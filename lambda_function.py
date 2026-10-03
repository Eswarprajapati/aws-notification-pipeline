"""S3 Lambda adapter. Outputs go to a separate bucket to avoid trigger loops."""
import os
from urllib.parse import unquote_plus
from processor import process_object

def lambda_handler(event,context,client=None):
    if client is None:
        import boto3
        client=boto3.client('s3')
    results=[]
    for record in event.get('Records',[]):
        if record.get('eventSource')!='aws:s3': continue
        obj=record['s3']['object']; key=unquote_plus(obj['key'])
        if not key.startswith('incoming/') or not key.endswith('.csv'): continue
        bucket=record['s3']['bucket']['name']; output=os.environ['OUTPUT_BUCKET']
        if bucket==output: raise ValueError('Input and output buckets must differ')
        result=process_object(client,bucket,key,output,obj.get('versionId'))
        # Metrics only; no recipient or message contents in CloudWatch logs.
        print({'event':'csv_processed','accepted':result['accepted'],'rejected':result['rejected']})
        results.append(result)
    return {'processed_objects':len(results),'results':results}
