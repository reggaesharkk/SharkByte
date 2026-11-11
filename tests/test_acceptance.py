import contextlib, io, json, os, pathlib, tempfile, unittest
from unittest import mock
from sharkbyte_alpha import cli, hybrid, quantum
import sharkbyte_guarded_entry

def invoke(args):
    out,err=io.StringIO(),io.StringIO()
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):status=cli.main(args)
    return status,out.getvalue(),err.getvalue()

class Acceptance(unittest.TestCase):
    def test_summary_preserves_full_record_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            target=str(pathlib.Path(d)/'result.json')
            status,out,_=invoke(['run','examples/adaptive.sb','--mode','hybrid','--summary','--output',target])
            self.assertEqual(status,0);self.assertIn('Iterations: 4',out);self.assertIn('Complete JSON record:',out)
            record=json.loads(pathlib.Path(target).read_text());self.assertEqual(cli.verify(record)['status'],'INTEGRITY_VERIFIED')
            self.assertEqual(record['result']['iterations_executed'],4)
            self.assertNotIn('No iterative quantum-classical loops yet',json.dumps(record))
            self.assertIn('bounded iteration is provided by the outer hybrid orchestrator',json.dumps(record))
            self.assertNotEqual(invoke(['run','examples/example.sb','--output',target])[0],0)
    def test_summary_needs_output(self):
        status,_,err=invoke(['run','examples/example.sb','--summary']);self.assertEqual(status,1);self.assertIn('requires --output',err)
    def test_conflicting_pythonpath_refused(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d)/'sharkbyte_alpha').mkdir()
            with mock.patch.dict(os.environ,{'PYTHONPATH':d}),contextlib.redirect_stderr(io.StringIO()) as err:
                status=sharkbyte_guarded_entry.main()
            self.assertEqual(status,2);self.assertIn('conflicting SharkByte installation',err.getvalue())
    def test_quantum_limits_and_recovery(self):
        for source in ('qubits 0;measure_all;','qubits 6;shots 100001;measure_all;','qubits 2;cp 999 0 1;measure_all;'):
            with self.assertRaises(ValueError):quantum.parse(source)
        self.assertEqual(invoke(['run','examples/example.sb'])[0],0)
    def test_maximum_hybrid_iterations(self):
        source=pathlib.Path('examples/adaptive.sb').read_text().replace('iterations = 4','iterations = 8').replace('shots = 2048','shots = 16').replace('count_00 < 1750','count_00 < 0')
        result=hybrid.run(source);self.assertEqual(result['iterations_executed'],8)
        self.assertEqual(len(result['history']),8)
        with self.assertRaises(ValueError):hybrid.run(source.replace('iterations = 8','iterations = 9'))
    def test_reject_changed_source_hash(self):
        status,out,_=invoke(['run','examples/example.sb']);self.assertEqual(status,0)
        record=json.loads(out);record['source']+=' '
        with self.assertRaises(ValueError):cli.verify(record)
    def test_hybrid_six_qubits_eight_iterations_and_false_branch(self):
        source=pathlib.Path('examples/adaptive.sb').read_text().replace('qubits = 2','qubits = 6').replace('iterations = 4','iterations = 8').replace('shots = 2048','shots = 16').replace('count_00 > count_11','count_000000 < 0').replace('count_00 < 1750','count_000000 < 0').replace('print count_00','print count_000000')
        result=hybrid.run(source)
        self.assertEqual(result['iterations_executed'],8)
        self.assertTrue(all(row['condition_result'] is False for row in result['history']))
        self.assertTrue(all(row['feedback_stdout'].endswith('0\n') for row in result['history']))

if __name__=='__main__':unittest.main(verbosity=2)
