import json
import asyncio
import subprocess
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logger = logging.getLogger(__name__)

# ThreadPoolExecutor for running subprocesses asynchronously
executor = ThreadPoolExecutor(max_workers=4)

class RunCodeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        logger.info("WebSocket connection accepted.")
        # Store process and input buffer state
        self.process = None
        self.input_buffer = ""
        self.expecting_input = False
        self.process_future = None
        self.stdout_task = None
        self.stderr_task = None

    async def disconnect(self, close_code):
        # Cleanup: Kill any running process when client disconnects
        await self.cleanup_process()
        logger.info(f"WebSocket disconnected with close code: {close_code}")

    async def cleanup_process(self):
        """Clean up any running process and tasks"""
        # Cancel running tasks
        if self.stdout_task and not self.stdout_task.done():
            self.stdout_task.cancel()
        if self.stderr_task and not self.stderr_task.done():
            self.stderr_task.cancel()
        if self.process_future and not self.process_future.done():
            self.process_future.cancel()
            
        # Kill process if running
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                await asyncio.sleep(0.1)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception as e:
                logger.error(f"Error cleaning up process: {e}")

    async def receive(self, text_data):
        # Parse incoming message
        try:
            data = json.loads(text_data)
            logger.debug(f"Received data: {data}")
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'error': 'Invalid JSON'}))
            return

        # Handle code execution request
        if 'code' in data:
            code = data.get('code', '')
            logger.info(f"Received code to execute: {code[:50]}...")
            
            # Clean up any existing process
            await self.cleanup_process()
            
            # Clear terminal
            await self.send(text_data=json.dumps({'clear': True}))
            
            # Start a new execution
            self.expecting_input = False
            await self.execute_code(code)
        
        # Handle input data for running process
        elif 'input' in data:
            input_text = data.get('input', '')
            logger.info(f"Received input: {input_text}")
            
            if self.process and self.process.poll() is None:
                # Write input to stdin and send a newline
                try:
                    logger.info("Writing input to process")
                    self.process.stdin.write(input_text + '\n')
                    self.process.stdin.flush()
                    
                    # Echo input to terminal
                    await self.send(text_data=json.dumps({
                        'output': input_text + '\n',
                        'stream': 'echo'
                    }))
                    
                except (BrokenPipeError, OSError) as e:
                    logger.error(f"Error writing to process: {e}")
                    await self.send(text_data=json.dumps({
                        'error': 'Process no longer accepting input'
                    }))
            else:
                await self.send(text_data=json.dumps({
                    'error': 'No process waiting for input'
                }))

    async def execute_code(self, code):
        try:
            # Start the process
            self.process = subprocess.Popen(
                ['python', '-u', '-c', code],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0  # Unbuffered
            )
            
            # Start async reading of stdout and stderr
            self.stdout_task = asyncio.create_task(self.read_stream(self.process.stdout, 'stdout'))
            self.stderr_task = asyncio.create_task(self.read_stream(self.process.stderr, 'stderr'))
            
            # Wait for process completion
            self.process_future = asyncio.create_task(self.wait_for_process())
            
        except Exception as e:
            logger.error(f"Error executing code: {e}")
            await self.send(text_data=json.dumps({
                'error': f'Error executing code: {str(e)}'
            }))

    async def read_stream(self, stream, stream_name):
        """Read from a stream character by character for real-time output."""
        try:
            while True:
                # Read a character
                char = await asyncio.get_event_loop().run_in_executor(executor, stream.read, 1)
                if not char:
                    break
                
                # Send the character to the client
                await self.send(text_data=json.dumps({
                    'output': char,
                    'stream': stream_name
                }))
                
                # If we're reading from stdout, check for input prompts
                # This is a heuristic and might need adjustment
                if stream_name == 'stdout' and char in [':', '?', '>'] and not self.input_buffer:
                    self.expecting_input = True
                    logger.info(f"Detected possible input prompt after character: {char}")
        except Exception as e:
            logger.error(f"Error reading from {stream_name}: {e}")
            if not self.process or self.process.poll() is not None:
                # Only report error if not due to process termination
                await self.send(text_data=json.dumps({
                    'error': f'Error reading from {stream_name}: {str(e)}'
                }))

    async def wait_for_process(self):
        """Wait for process to complete and send finished signal."""
        try:
            returncode = await asyncio.get_event_loop().run_in_executor(
                executor, self.process.wait
            )
            logger.info(f"Process completed with return code: {returncode}")
            
            # Allow any final output to be processed
            await asyncio.sleep(0.1)
            
            await self.send(text_data=json.dumps({
                'finished': True,
                'returncode': returncode
            }))
        except Exception as e:
            logger.error(f"Error waiting for process: {e}")
            await self.send(text_data=json.dumps({
                'error': f'Error during execution: {str(e)}'
            }))