import os
os.chdir('/home/ubuntu/Financial_analysis_fyp/backend')
from dotenv import load_dotenv
load_dotenv()
fast = os.environ.get('FAST_MODEL', 'NOT SET')
print(f'FAST_MODEL from os.environ: {fast}')
import sys
sys.path.insert(0, '/home/ubuntu/Financial_analysis_fyp')
import config.settings as s
print(f'config.settings.FAST_MODEL: {s.FAST_MODEL}')
print(f'config.settings.LLM_PROVIDER: {s.LLM_PROVIDER}')
