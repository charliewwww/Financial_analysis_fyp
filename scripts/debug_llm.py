import sys, os
os.chdir('/home/ubuntu/Financial_analysis_fyp/backend')
sys.path.insert(0, '/home/ubuntu/Financial_analysis_fyp')
import config.settings as s
print(f'LLM_PROVIDER={s.LLM_PROVIDER}')
print(f'FAST_MODEL={s.FAST_MODEL}')
print(f'LLM_BASE_URL={s.LLM_BASE_URL}')
print(f'DEEPSEEK_API_KEY set={bool(s.DEEPSEEK_API_KEY)}')
