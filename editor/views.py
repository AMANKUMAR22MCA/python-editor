import subprocess
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import tempfile
import os
from django.http import JsonResponse
import json

def editor_view(request):
    return render(request, 'editor.html')


# @csrf_exempt
# def run_code(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             code = data.get('code', '')
#             user_input = data.get('input', '')
#         except json.JSONDecodeError:
#             return JsonResponse({'error': 'Invalid JSON'}, status=400)

#         # Wrapper to modify input() so prompt prints with newline
#         input_wrapper = '''
# import builtins
# original_input = builtins.input
# def input(prompt=''):
#     print(prompt)
#     return original_input('')
# builtins.input = input
# '''

#         full_code = input_wrapper + '\n' + code

#         # Create temp file and close it immediately so subprocess can access it
#         with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
#             tmp.write(full_code.encode())
#             tmp.flush()
#             tmp_name = tmp.name

#         try:
#             result = subprocess.run(
#                 ['python', tmp_name],  # or 'python3'
#                 input=user_input.encode(),
#                 capture_output=True,
#                 timeout=5
#             )
#             output = result.stdout.decode()
#             error = result.stderr.decode()
#         except Exception as e:
#             output = ''
#             error = str(e)
#         finally:
#             if os.path.exists(tmp_name):
#                 os.unlink(tmp_name)

#         return JsonResponse({'output': output, 'error': error})