import sys
sys.path.insert(0, '/home/ubuntu/Financial_analysis_fyp')
from agents.llm_client import check_llm_health
try:
    check_llm_health(timeout=10)
    print('LLM HEALTH: OK')
except Exception as e:
    print(f'LLM HEALTH FAIL: {e}')
