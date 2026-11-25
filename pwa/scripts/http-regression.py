"""Full HTTP workflow contract checks, restricted to the disposable local regression site."""
import base64
import json
from pathlib import Path
from uuid import uuid4
import requests

BASE='http://127.0.0.1:8002'
API='volunteering.volunteering.collaboration_mobile.'
PWA='volunteering.volunteering.tasks_pwa.'
PASSWORD='DemoChat!2026'
USERS={role:f'demo.chat.{name}@sevamrita.local' for role,name in [('owner','ravi'),('member','arjun'),('viewer','dev')]}
report=[]

class Client:
    def __init__(self,email):
        self.http=requests.Session()
        response=self.http.post(BASE+'/api/method/login',json={'usr':email,'pwd':PASSWORD},timeout=20)
        assert response.status_code==200, f'Cannot log in {email}'
        self.user=email
        self.csrf=self.http.get(BASE+'/api/method/'+PWA+'get_session',timeout=20).json()['message']['csrf_token']
    def call(self,method,args=None,status=200):
        response=self.http.post(BASE+'/api/method/'+method,json=args or {},headers={'X-Frappe-CSRF-Token':self.csrf},timeout=30)
        assert response.status_code==status,(method,response.status_code,response.text[:500])
        return response.json().get('message')
    def app(self,method,args=None,status=200):return self.call(API+method,args,status)
    def operation(self,method,payload,key=None,status=200):return self.call(PWA+'apply_operation',{'method':method,'payload':payload,'request_key':key or str(uuid4()),'expected_user':self.user},status)

owner=Client(USERS['owner']);member=Client(USERS['member']);viewer=Client(USERS['viewer'])
assert owner.app('get_collaboration_home')['isolated_test_site'], 'Refuse test writes outside the isolated database'
room=None
try:
    shell=owner.http.get(BASE+'/sf-tasks/',timeout=20)
    assert shell.status_code==200 and 'manifest.webmanifest' in shell.text
    worker=owner.http.get(BASE+'/api/method/'+PWA+'service_worker',timeout=20)
    assert worker.status_code==200 and worker.headers['Service-Worker-Allowed']=='/sf-tasks/' and '?v=' in worker.text
    manifest=owner.http.get(BASE+'/assets/volunteering/sf_tasks/manifest.webmanifest',timeout=20).json()
    assert manifest['id']=='/sf-tasks/' and manifest['name']=='SF Tasks PWA'
    report.append('Separate install identity, public app shell and limited service-worker scope')
    room=owner.app('save_space',{'payload':{'title':'PWA contract QA '+str(uuid4())[:8],'space_kind':'Workspace','members':[{'user':USERS['owner'],'access_level':'Owner'},{'user':USERS['member'],'access_level':'Member'},{'user':USERS['viewer'],'access_level':'Viewer'}]}})['name']
    report.append('Workspace creation and membership')
    message={'payload':{'space':room,'body':'Please coordinate the supplies, @[Arjun Sharma]('+USERS['member']+').','request_key':str(uuid4()),'entry_kind':'Message','attachments':[{'filename':'pwa-plan.txt','content':base64.b64encode(b'Community kitchen QA plan').decode()}]}}
    replay=str(uuid4());first=owner.operation('send_message',message,replay);again=owner.operation('send_message',message,replay)
    assert first['name']==again['name']
    entries=member.app('get_space',{'name':room})['entries'];entry=next(e for e in entries if e['name']==first['name'])
    assert len(entry['attachments'])==1
    url=entry['attachments'][0]['file_url']
    assert member.http.get(BASE+url,timeout=20).content==b'Community kitchen QA plan'
    assert requests.get(BASE+url,timeout=20).status_code in {401,403}
    member.app('mark_delivered',{'space':room,'entry':entry['name']});member.app('mark_seen',{'space':room,'entry':entry['name']})
    assert next(p for p in owner.app('get_message_info',{'name':entry['name']})['recipients'] if p['user']==USERS['member'])['status']==3
    mentions=member.app('get_mentions')
    assert entry['name'] in [e['name'] for e in mentions['mentions']]
    member.app('mark_mention_seen',{'entry':entry['name']})
    owner.app('edit_entry',{'name':entry['name'],'body':'Supplies confirmed.','expected_modified':entry['modified']})
    report.append('Idempotent messages, private attachments, mentions, edits and read receipts')
    viewer.app('post_entry',{'space':room,'body':'Not permitted','request_key':str(uuid4())},403)
    report.append('Viewer cannot send messages')
    task=owner.operation('save_item',{'space':room,'payload':{'item_kind':'Task','title':'Confirm delivery route','assignee':USERS['member'],'from_date':'2026-11-09','until_date':'2026-11-11','deadline':'2026-11-11','item_data':{'subtasks':[{'id':'route','title':'Check address','assignee':USERS['member'],'deadline':'2026-11-10','status':'Open'}]}}})
    task=member.operation('update_task',{'name':task['name'],'action':'start','expected_modified':task['modified']})
    assert task['status']=='In progress'
    member.operation('update_task',{'name':task['name'],'action':'complete','expected_modified':task['modified']},status=417)
    task=member.operation('update_subtask',{'name':task['name'],'subtask':'route','status':'Completed','expected_modified':task['modified']})
    task=member.operation('update_task',{'name':task['name'],'action':'complete','expected_modified':task['modified']})
    assert task['status']=='Completed'
    report.append('Task In progress, assigned subtasks, deadline and completion validation')
    tracker=owner.operation('save_item',{'space':room,'payload':{'item_kind':'Tracker','title':'Kitchen delivery handover','item_data':{'scale':'Status','assignment_mode':'Stages','stages':[{'key':'prepare','label':'Preparation','assignee':USERS['owner']},{'key':'deliver','label':'Delivery','assignee':USERS['member']}],'attention_date':'2026-11-09'}}})
    tracker=owner.operation('record_progress',{'name':tracker['name'],'expected_modified':tracker['modified'],'note':'Meals packed.','stage':'prepare','request_key':str(uuid4())})
    tracker=member.operation('record_progress',{'name':tracker['name'],'expected_modified':tracker['modified'],'note':'Ready for delivery.','stage':'deliver','request_key':str(uuid4())})
    current=owner.app('get_space',{'name':room})
    updates=[e for e in current['entries'] if e['entry_kind']=='Progress']
    assert len(updates)==2 and current['current_progress'][tracker['name']]==updates[-1]['name']
    tracker=owner.operation('add_tracker_files',{'name':tracker['name'],'expected_modified':tracker['modified'],'attachments':[{'filename':'handover.txt','content':base64.b64encode(b'Handover checked').decode()}],'request_key':str(uuid4()),'note':'Handover proof'})
    assert owner.app('get_tracker_files',{'name':tracker['name']})['files']
    member.operation('post_comment',{'name':tracker['name'],'body':'The volunteers are ready.','request_key':str(uuid4())})
    assert owner.app('get_comments',{'name':tracker['name']})['comments'][0]['body']=='The volunteers are ready.'
    assert tracker['name'] in [t['name'] for t in member.call(PWA+'get_work')['trackers']]
    report.append('Multi-person status tracker, current/older progress, comments and tracker files')
    event=owner.operation('save_item',{'space':room,'payload':{'item_kind':'Event','title':'Kitchen handover call','start_at':'2026-11-10 09:00:00','end_at':'2026-11-10 09:30:00','participants':[USERS['member']],'location':'Pune office'}})
    checklist=owner.operation('save_item',{'space':room,'payload':{'item_kind':'List','title':'Delivery checklist','item_data':{'rows':[{'id':'supplies','content':'Check supplies','completed':False,'priority':'High'}]}}})
    assert event['name'] in [e['name'] for e in member.call(PWA+'get_work',{'date':'2026-11-10'})['calendar']]
    assert checklist['name'] in [e['name'] for e in member.app('get_space',{'name':room})['items']]
    found=owner.app('search_conversation',{'query':'handover','kind':'All','space':room})
    assert found['results']
    report.append('Events, calendar, lists and cross-content search')
finally:
    if room:
        snapshot=owner.app('get_space',{'name':room})['space']
        owner.app('save_space',{'name':room,'expected_modified':snapshot['modified'],'payload':{'archived':True}})
print(json.dumps({'passed':len(report),'checks':report,'test_workspace_archived':bool(room)},indent=2))
