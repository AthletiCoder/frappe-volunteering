import base64
from datetime import datetime
from unittest.mock import patch
import frappe
from frappe.tests import IntegrationTestCase
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from volunteering.volunteering import tasks_pwa as pwa, tasks_web_push as push, collaboration_mobile as app
from volunteering.volunteering.collaboration_access import APP_ROLE, WEB_ROLE, chat_channel
from volunteering.volunteering.accounting_test_utils import get_or_create_user
from volunteering.volunteering.collaboration_setup import ensure_chat_role


class IntegrationTestTasksPWA(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user('Administrator')
        ensure_chat_role()
        with patch('frappe.utils.global_search.sync_value_in_queue'):
            cls.owner=get_or_create_user('pwa-owner@example.com',[APP_ROLE],first_name='PWA Owner')
            cls.other=get_or_create_user('pwa-other@example.com',[APP_ROLE],first_name='PWA Other')
            cls.web=get_or_create_user('pwa-web@example.com',[WEB_ROLE],first_name='PWA Web')

    def setUp(self):
        super().setUp()
        self.queue_patch=patch('frappe.enqueue')
        self.queue_patch.start()
        self.addCleanup(self.queue_patch.stop)
        frappe.db.savepoint('pwa_case')
        frappe.set_user(self.owner)

    def tearDown(self):
        frappe.set_user('Administrator')
        frappe.db.rollback(save_point='pwa_case')
        super().tearDown()

    def subscription(self,endpoint='https://fcm.googleapis.com/fcm/send/pwa-test-token'):
        key=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        return {'endpoint':endpoint,'keys':{'p256dh':push._b64(key),'auth':push._b64(b'0123456789abcdef')}}

    def test_worker_is_public_javascript_with_scope_limited_to_the_separate_app(self):
        frappe.set_user('Guest')
        response=pwa.service_worker()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['Service-Worker-Allowed'],'/sf-tasks/')
        self.assertIn('/assets/volunteering/sf_tasks/assets/worker-',response.get_data(as_text=True))
        self.assertIn('no-store',response.headers['Cache-Control'])

    def test_work_requires_app_role_and_restores_context(self):
        frappe.set_user(self.web)
        with self.assertRaises(frappe.PermissionError):pwa.get_work()
        frappe.set_user(self.owner)
        self.assertIn('trackers',pwa.get_work())
        self.assertEqual(chat_channel.get(),'web')

    def test_dashboard_shows_member_trackers_without_hierarchy_access(self):
        room=app.save_space({'title':'PWA group','members':[{'user':self.owner,'access_level':'Owner'},{'user':self.other,'access_level':'Member'}]})['name']
        tracker=app.save_item(room,{'title':'Assigned to someone else','item_kind':'Tracker','assignee':self.owner,'item_data':{'scale':'Percentage'}})
        frappe.set_user(self.other)
        self.assertIn(tracker['name'],[t['name'] for t in pwa.get_work()['trackers']])
        frappe.set_user(self.web)
        with self.assertRaises(frappe.PermissionError):pwa.get_work()

    def test_item_share_is_visible_without_exposing_chat_content(self):
        room=app.save_space({'title':'Private PWA group'})['name']
        tracker=app.save_item(room,{'title':'Shared tracker','item_kind':'Tracker','item_data':{'scale':'Percentage'}})
        app.share_item(tracker['name'],[{'user':self.other,'access':'View'}],tracker['modified'])
        frappe.set_user(self.other)
        self.assertIn(tracker['name'],[t['name'] for t in pwa.get_work()['trackers']])
        self.assertTrue(app.get_work_item(tracker['name'])['item_only'])
        with self.assertRaises(frappe.PermissionError):app.get_space(room)

    def test_subscription_rejects_arbitrary_urls_and_invalid_crypto_keys(self):
        for endpoint in ['http://fcm.googleapis.com/x','https://127.0.0.1/private','https://evil.example/x','https://fcm.googleapis.com.evil.example/x','https://user@fcm.googleapis.com/x','https://fcm.googleapis.com:444/x']:
            with self.subTest(endpoint=endpoint),self.assertRaises(frappe.ValidationError):push.clean_subscription(self.subscription(endpoint))
        invalid=self.subscription();invalid['keys']['auth']='bad'
        with self.assertRaises(frappe.ValidationError):push.clean_subscription(invalid)

    def test_subscription_is_encrypted_and_bound_to_current_account(self):
        sub=self.subscription()
        binding='00000000-0000-0000-0000-000000000001'
        push.subscribe(sub,binding)
        doc=frappe.get_doc(push.DEVICE,frappe.db.get_value(push.DEVICE,{'user':self.owner},'name'))
        self.assertNotIn(sub['endpoint'],frappe.db.get_value(push.DEVICE,doc.name,'subscription') or '')
        self.assertEqual(frappe.parse_json(doc.get_password('subscription'))['endpoint'],sub['endpoint'])
        frappe.set_user(self.other)
        push.subscribe(sub,'00000000-0000-0000-0000-000000000002')
        self.assertEqual(frappe.db.get_value(push.DEVICE,doc.name,'user'),self.other)

    def test_web_only_role_cannot_register_notifications(self):
        frappe.set_user(self.web)
        with self.assertRaises(frappe.PermissionError):push.subscribe(self.subscription(),'00000000-0000-0000-0000-000000000001')

    def test_vapid_identity_is_stable_and_contains_no_private_key_in_public_config(self):
        first=push.get_config()
        self.assertEqual(first,push.get_config())
        self.assertEqual(len(base64.urlsafe_b64decode(first['public_key']+'=')),65)
        self.assertEqual(set(first),{'enabled','public_key'})

    def test_preferences_and_overnight_quiet_hours(self):
        prefs=push.clean_preferences({'mode':'Mentions','quiet_from':'22:00','quiet_until':'08:00'})
        self.assertEqual(push._quiet_end(prefs,datetime(2026,11,8,23,0)),datetime(2026,11,9,8,0))
        self.assertEqual(push._quiet_end(prefs,datetime(2026,11,8,7,0)),datetime(2026,11,8,8,0))
        self.assertIsNone(push._quiet_end(prefs,datetime(2026,11,8,12,0)))
        with self.assertRaises(frappe.ValidationError):push.clean_preferences({'mode':'All','quiet_from':'25:00'})

    def test_duplicate_notification_event_queues_once_per_binding(self):
        push.subscribe(self.subscription(),'00000000-0000-0000-0000-000000000001')
        device=frappe.get_doc(push.DEVICE,frappe.db.get_value(push.DEVICE,{'user':self.owner},'name'))
        push._notice(device,'event-1',{'kind':'message','space':'test'})
        push._notice(device,'event-1',{'kind':'message','space':'test'})
        self.assertEqual(frappe.db.count(push.NOTICE,{'device':device.name}),1)

    def test_unsubscribe_cannot_disable_another_users_browser(self):
        binding='00000000-0000-0000-0000-000000000001'
        push.subscribe(self.subscription(),binding)
        name=frappe.db.get_value(push.DEVICE,{'user':self.owner},'name')
        frappe.set_user(self.other)
        push.unsubscribe(binding)
        self.assertTrue(frappe.db.get_value(push.DEVICE,name,'enabled'))

    def test_late_membership_removal_prevents_queued_push(self):
        room=app.save_space({'title':'PWA privacy check','members':[{'user':self.owner,'access_level':'Owner'},{'user':self.other,'access_level':'Member'}]})['name']
        frappe.set_user(self.other)
        push.subscribe(self.subscription(),'00000000-0000-0000-0000-000000000001')
        frappe.set_user(self.owner)
        entry=app.post_entry(room,'Confidential kitchen note',request_key='pwa-notification-privacy')
        notice=frappe.db.get_value(push.NOTICE,{'status':'Pending'},'name')
        data=app.get_space(room)
        app.save_space({'members':[{'user':self.owner,'access_level':'Owner'}]},name=room,expected_modified=data['space']['modified'])
        with patch('pywebpush.webpush') as sender:
            push.deliver(notice)
            sender.assert_not_called()
        self.assertEqual(frappe.db.get_value(push.NOTICE,notice,'status'),'Skipped')

    def test_webpush_contains_only_routing_ids_not_private_message_text(self):
        room=app.save_space({'title':'Private PWA room','members':[{'user':self.owner,'access_level':'Owner'},{'user':self.other,'access_level':'Member'}]})['name']
        frappe.set_user(self.other)
        push.subscribe(self.subscription(),'00000000-0000-0000-0000-000000000001')
        frappe.set_user(self.owner)
        app.post_entry(room,'Sensitive test text should stay in ERP',request_key='pwa-content-free')
        notice=frappe.db.get_value(push.NOTICE,{'status':'Pending'},'name')
        with patch('pywebpush.webpush') as sender:
            push.deliver(notice)
            payload=frappe.parse_json(sender.call_args.kwargs['data'])
            self.assertNotIn('Sensitive test text',sender.call_args.kwargs['data'])
            self.assertNotIn('title',payload)
        self.assertEqual(frappe.db.get_value(push.NOTICE,notice,'status'),'Sent')

    def test_stale_subscriptions_are_disabled_after_push_service_expiry(self):
        import requests
        from pywebpush import WebPushException
        room=app.save_space({'title':'PWA expired browser','members':[{'user':self.owner,'access_level':'Owner'},{'user':self.other,'access_level':'Member'}]})['name']
        frappe.set_user(self.other)
        push.subscribe(self.subscription(),'00000000-0000-0000-0000-000000000001')
        device=frappe.db.get_value(push.DEVICE,{'user':self.other},'name')
        frappe.set_user(self.owner)
        app.post_entry(room,'Check expired browser',request_key='pwa-expired')
        notice=frappe.db.get_value(push.NOTICE,{'device':device,'status':'Pending'},'name')
        response=requests.Response();response.status_code=410
        with patch('pywebpush.webpush',side_effect=WebPushException('Gone',response=response)):
            push.deliver(notice)
        self.assertFalse(frappe.db.get_value(push.DEVICE,device,'enabled'))
        self.assertEqual(frappe.db.get_value(push.NOTICE,notice,'status'),'Skipped')

    def test_transient_push_network_failure_retries_without_exposing_keys(self):
        import requests
        room=app.save_space({'title':'PWA network retry','members':[{'user':self.owner,'access_level':'Owner'},{'user':self.other,'access_level':'Member'}]})['name']
        frappe.set_user(self.other)
        push.subscribe(self.subscription(),'00000000-0000-0000-0000-000000000001')
        device=frappe.db.get_value(push.DEVICE,{'user':self.other},'name')
        frappe.set_user(self.owner)
        app.post_entry(room,'Network retry',request_key='pwa-retry')
        notice=frappe.db.get_value(push.NOTICE,{'device':device,'status':'Pending'},'name')
        with patch('pywebpush.webpush',side_effect=requests.ConnectionError('Offline')):
            push.deliver(notice)
        self.assertEqual(frappe.db.get_value(push.NOTICE,notice,'status'),'Pending')
        self.assertEqual(frappe.db.get_value(push.NOTICE,notice,'attempts'),1)

    def test_vapid_key_signs_a_real_webpush_authorization_without_network(self):
        from py_vapid import Vapid
        key=push._identity().private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption())
        identity=Vapid.from_string(push._b64(key))
        headers=identity.sign({'aud':'https://fcm.googleapis.com','sub':'https://sevamrita.org'})
        self.assertIn('Authorization',headers)

    def test_durable_operation_rechecks_expected_account_in_the_mutation_request(self):
        room=app.save_space({'title':'PWA scoped outbox'})['name']
        with self.assertRaises(frappe.PermissionError):
            pwa.apply_operation('send_message',{'payload':{'space':room,'body':'wrong account','request_key':'body'}},'wrong-user',self.other)
        self.assertEqual(len(app.get_space(room)['entries']),0)
        result=pwa.apply_operation('send_message',{'payload':{'space':room,'body':'right account','request_key':'body'}},'right-user',self.owner)
        self.assertTrue(result['name'])
