import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from audit import AuditLedger, Meta, add_nodes, compare_snapshots, run_bundle

M = dict(qkind='stock', unit='t C', period='instant:2021', support='municipality')

class AuditTests(unittest.TestCase):
    def test_exact_sum_and_product(self):
        L = AuditLedger()
        for k, v in [('a', 3), ('b', 7)]:
            L.put(k, v, Meta(**M), 's', '1')
        L.derive('sum', 'sum', ['a', 'b'], Meta(**M))
        L.derive('product', 'mul', ['a', 'b'], Meta(**M))
        self.assertEqual(L.d['sum'].value, 10)
        self.assertEqual(L.d['product'].value, 21)

    def test_orphan_reappears_and_resolves(self):
        L = AuditLedger()
        L.register_source('s', '1')
        L.put('a', 8, Meta(**M), 's', '1')
        L.derive('out', 'scale', ['a'], Meta(**M), k=2)
        L.apply_update('s', '2', {})
        self.assertEqual((L.d['out'].status, L.d['out'].value), ('orphan', None))
        L.apply_update('s', '3', {'a': (9, Meta(**M))})
        self.assertEqual((L.d['out'].status, L.d['out'].value), ('ok', 18))

    def test_contract_blocks_number_and_descendants(self):
        L = AuditLedger()
        L.put('a', 8, Meta(**M), 's', '1')
        L.put('b', 2, Meta('flux', 't C', 'annual:2021', 'municipality'), 's', '1')
        L.derive('bad', 'diff', ['a', 'b'], Meta(**M))
        L.derive('child', 'scale', ['bad'], Meta(**M), k=2)
        self.assertEqual((L.d['bad'].status, L.d['bad'].value), ('blocked', None))
        self.assertEqual((L.d['child'].status, L.d['child'].value), ('blocked', None))

    def test_unresolved_is_distinct_from_orphan(self):
        L = AuditLedger()
        L.derive('out', 'scale', ['unknown'], Meta(**M), k=2)
        self.assertEqual(L.d['out'].status, 'unresolved')

    def test_new_context_reorders_existing_consumers(self):
        L = AuditLedger()
        L.put('a', 3, Meta(**M), 's', '1')
        L.derive('total', 'sum', ['a'], Meta(**M))
        L.derive('twice', 'scale', ['total'], Meta(**M), k=2)
        L.put('b', 7, Meta(**M), 's', '2')
        L.derive('new', 'scale', ['b'], Meta(**M), k=3)
        L.rewire({'total': ['a', 'new']})
        self.assertEqual((L.d['total'].value, L.d['twice'].value), (24, 48))
        self.assertLess(L.order.index('new'), L.order.index('total'))

    def test_cycle_fails_before_mutation(self):
        L = AuditLedger()
        L.put('a', 3, Meta(**M), 's', '1')
        L.derive('total', 'sum', ['a'], Meta(**M))
        L.derive('twice', 'scale', ['total'], Meta(**M), k=2)
        before = copy.deepcopy(L.der)
        with self.assertRaisesRegex(ValueError, 'cycle'):
            L.rewire({'total': ['twice']})
        self.assertEqual(L.der, before)

    def test_new_outputs_count_as_changes(self):
        r = compare_snapshots({'a': (2, 'ok')}, {'a': (2, 'ok'), 'new': (3, 'ok')}, {'new'})
        self.assertEqual((r['changed'], r['new_outputs'], r['recall']), (1, 1, 1))

    def test_duplicate_keys_rejected(self):
        bundle = {'sources': [{'name': 's', 'version': '1', 'contract': M, 'csv': 'key,value\na,1\na,2\n'}]}
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            run_bundle(bundle)

    def test_unit_alias_is_not_conversion(self):
        L = AuditLedger()
        L.register_source('s', '1')
        meta = Meta('flux', 'CH4 * gigagram/ a', 'annual:2021', 'country')
        L.put('a', 3, meta, 's', '1')
        diff = L.diff_source('s', {'a': (3, Meta('flux', 'CH4 * gigagram/ yr', 'annual:2021', 'country'))})
        self.assertEqual(diff['contract_changed'], [])
        diff = L.diff_source('s', {'a': (3000, Meta('flux', 'CH4 * ton/ yr', 'annual:2021', 'country'))})
        self.assertEqual(diff['contract_changed'], ['a'])

    def test_zero_denominator(self):
        L = AuditLedger()
        L.put('a', 3, Meta(**M), 's', '1')
        L.put('b', 0, Meta(**M), 's', '1')
        L.derive('r', 'ratio', ['a', 'b'], Meta('share', '1', 'instant:2021', 'municipality'))
        self.assertEqual((L.d['r'].value, L.d['r'].status), (None, 'unresolved'))

    def test_sum_does_not_mix_years(self):
        L = AuditLedger()
        L.put('a', 3, Meta(**M), 's', '1')
        L.put('b', 4, Meta('stock', 't C', 'instant:2020', 'municipality'), 's', '1')
        L.derive('total', 'sum', ['a', 'b'], Meta(**M))
        self.assertEqual((L.d['total'].value, L.d['total'].status), (None, 'blocked'))

    def test_example_has_values_from_independent_arithmetic(self):
        import json
        path = Path(__file__).resolve().parents[1] / 'examples' / 'soil_plan.json'
        result = run_bundle(json.loads(path.read_text(encoding='utf-8')))
        self.assertEqual(result['revisions'][0]['before']['total']['value'], 500)
        self.assertEqual(result['revisions'][0]['after']['total']['value'], 530)
        self.assertEqual(result['revisions'][1]['after']['total']['value'], 590)
        self.assertEqual(result['revisions'][2]['after']['total']['status'], 'orphan')

    def test_nodes_can_be_declared_before_dependencies(self):
        L = AuditLedger()
        L.put('a', 3, Meta(**M), 's', '1')
        add_nodes(L, [dict(key='second', op='scale', inputs=['first'], contract=M, params={'k':2}),
                      dict(key='first', op='scale', inputs=['a'], contract=M, params={'k':4})])
        self.assertEqual(L.d['second'].value, 24)

if __name__ == '__main__':
    unittest.main()
