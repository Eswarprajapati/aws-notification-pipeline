"""Validate notification CSVs and create deterministic processing artifacts."""
import csv
import hashlib
import io
import json
from datetime import datetime

REQUIRED={'notification_id','recipient','channel','message','created_at'}

def process_csv(payload):
    text=payload.decode('utf-8-sig') if isinstance(payload,bytes) else payload
    reader=csv.DictReader(io.StringIO(text))
    if not REQUIRED.issubset(set(reader.fieldnames or [])):
        raise ValueError('CSV is missing required columns')
    accepted=[]; rejected=[]; seen=set()
    for line,row in enumerate(reader,2):
        row={k:(v or '').strip() for k,v in row.items() if k is not None}
        errors=[]
        if None in reader.fieldnames or any(not row.get(k) for k in REQUIRED):
            errors.append('missing_value')
        if row.get('channel') not in {'email','sms','push'}:
            errors.append('invalid_channel')
        try:
            ts=datetime.fromisoformat(row.get('created_at','').replace('Z','+00:00'))
            if ts.tzinfo is None: errors.append('timestamp_requires_timezone')
        except ValueError:
            errors.append('invalid_timestamp')
        if row.get('notification_id') in seen: errors.append('duplicate_id')
        if errors:
            # Do not persist recipients or message contents in rejection logs.
            rejected.append({'line':line,'notification_id':row.get('notification_id'), 'errors':errors})
        else:
            seen.add(row['notification_id']); accepted.append(row)
    return {'accepted':accepted,'rejected':rejected,
            'summary':{'accepted':len(accepted),'rejected':len(rejected)}}

def process_object(client,bucket,key,output_bucket,version_id=None):
    args={'Bucket':bucket,'Key':key}
    if version_id: args['VersionId']=version_id
    payload=client.get_object(**args)['Body'].read()
    result=process_csv(payload)
    identity=json.dumps([bucket,key,version_id,hashlib.sha256(payload).hexdigest()])
    output_key='processed/'+hashlib.sha256(identity.encode()).hexdigest()+'.json'
    client.put_object(Bucket=output_bucket,Key=output_key,
                      Body=json.dumps(result,sort_keys=True).encode(),ContentType='application/json')
    return {'output_key':output_key,**result['summary']}
