import unittest


class RebindTest(unittest.IsolatedAsyncioTestCase):
    async def test_missing_instance_requires_observable_detach_before_attach(self):
        from scripts.warehouse_worker_behavior_rebind import ensure_instance
        state={'paths':['behavior.py'],'instance':None,'detached':False}
        def set_paths(paths):
            state['paths']=list(paths)
        async def tick():
            if not state['paths']:
                state['detached']=True
            elif state['detached']:
                state['instance']='running'
        result=await ensure_instance(lambda:state['instance'],set_paths,tick,['behavior.py'],5)
        self.assertEqual(result,'running')
        self.assertEqual(state['paths'],['behavior.py'])

    async def test_failed_load_restores_path_and_raises_not_ready(self):
        from scripts.warehouse_worker_behavior_rebind import ensure_instance
        paths=[]
        async def tick():
            pass
        with self.assertRaisesRegex(RuntimeError,'instance'):
            await ensure_instance(lambda:None,lambda p:paths.append(list(p)),tick,['a'],3)
        self.assertEqual(paths[-1],['a'])

    async def test_existing_instance_is_not_reinitialized(self):
        from scripts.warehouse_worker_behavior_rebind import ensure_instance
        writes=[]
        async def tick():
            self.fail('Existing instance should be reused')
        self.assertEqual(await ensure_instance(lambda:'running',writes.append,tick,['a'],3),'running')
        self.assertEqual(writes,[])
