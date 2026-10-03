from pathlib import Path
import json
from processor import process_csv
if __name__=='__main__':
    result=process_csv(Path('data/notifications.csv').read_bytes())
    Path('results').mkdir(exist_ok=True)
    Path('results/processed.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result['summary']))
