import io,os,unittest
from unittest.mock import patch
from pathlib import Path
from processor import process_csv,process_object
from lambda_function import lambda_handler

class MemoryS3:
    def __init__(self): self.writes={}; self.reads=[]
    def get_object(self,**kw):
        self.reads.append(kw)
        return {'Body':io.BytesIO(Path('data/notifications.csv').read_bytes())}
    def put_object(self,**kw): self.writes[kw['Key']]=kw['Body']

class NotificationTests(unittest.TestCase):
    def test_bad_rows_quarantined(self):
        r=process_csv(Path('data/notifications.csv').read_bytes())
        self.assertEqual(r['summary'],{'accepted':2,'rejected':2})
        self.assertEqual(r['rejected'][0]['errors'],['duplicate_id'])
    def test_required_schema(self):
        with self.assertRaises(ValueError): process_csv('id,message\n1,hi')
    def test_retry_writes_same_key(self):
        s=MemoryS3(); a=process_object(s,'raw','incoming/a.csv','out','v1')
        b=process_object(s,'raw','incoming/a.csv','out','v1')
        self.assertEqual(a,b); self.assertEqual(len(s.writes),1)
        self.assertEqual(s.reads[0]['VersionId'],'v1')
    def test_different_version_separate_artifact(self):
        s=MemoryS3(); a=process_object(s,'raw','incoming/a.csv','out','v1')
        b=process_object(s,'raw','incoming/a.csv','out','v2')
        self.assertNotEqual(a['output_key'],b['output_key'])
    def test_event_decodes_key(self):
        s=MemoryS3()
        e={'Records':[{'eventSource':'aws:s3','s3':{'bucket':{'name':'raw'},'object':{'key':'incoming/test+file.csv','versionId':'v1'}}}]}
        with patch.dict(os.environ,{'OUTPUT_BUCKET':'out'}):
            self.assertEqual(lambda_handler(e,None,s)['processed_objects'],1)
        self.assertEqual(s.reads[0]['Key'],'incoming/test file.csv')
    def test_non_input_events_ignored(self):
        e={'Records':[{'eventSource':'aws:s3','s3':{'bucket':{'name':'raw'},'object':{'key':'processed/out.json'}}}]}
        self.assertEqual(lambda_handler(e,None,MemoryS3())['processed_objects'],0)
    def test_rejection_has_no_recipient(self):
        r=process_csv(Path('data/notifications.csv').read_bytes())
        self.assertTrue(all('recipient' not in row for row in r['rejected']))
