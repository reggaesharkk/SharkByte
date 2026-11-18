"""Cross-check the nine submitted receipts against the pinned upstream vector field."""
import sys, json, hashlib
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
import verification_existence_v1_0 as ref
from sharkbyte_alpha import lucid_dynamics as m
if not __debug__:
    raise RuntimeError('Audit requires Python assertions enabled')
source = Path(ref.__file__).read_bytes()
assert hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\x00' + source).hexdigest() == '4b3b2b3195af9164a66e8f208b692fa6c24b7dc1'
files = sorted(Path(sys.argv[1]).glob('sharkbyte-*.json'))
assert len(files) == 9, 'Expected the nine original uploads'
cache = {}
for f in files:
    d = json.loads(f.read_bytes())
    h = d.pop('record_sha256')
    assert hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest() == h
    c = d['config']
    p = c['parameters']
    r = d['result']
    dg = r['diagnostics']
    t = np.array(r['t'])
    keys = ('gamma', 'H_obs', 'I_dot', 'Psi')
    y = np.array([r[k] for k in keys])
    assert c['model_constants'] == m.PARAMETERS and tuple(c['initial_state']) == m.INITIAL_STATE and (d['source']['commit'] == m.SOURCE_COMMIT)
    assert c['solver'] == dict(method='LSODA', rtol=1e-09, atol=1e-12, max_step=0.5) and dg['solver_success'] and (dg['nfev'] > 0)
    np.testing.assert_allclose(t, np.linspace(0, c['duration'], c['samples']))
    assert y.shape == (4, len(t)) and np.isfinite(y).all()
    np.testing.assert_allclose(y[:, 0], m.INITIAL_STATE)
    np.testing.assert_allclose(np.ptp(y[:, t >= 0.8 * t[-1]], axis=1), [dg['tail_range'][k] for k in keys])
    np.testing.assert_allclose(np.linalg.norm(y[:, -1]), dg['final_state_norm'])
    assert np.all(y.min(axis=1) >= -1e-08) and np.all(y.max(axis=1)[[0, 1, 3]] <= [10, 100, 1])
    args = tuple((p[k] for k in ('P_0', 'lambda_sim', 'lambda_lucid', 'kappa_meta')))
    if args not in cache:

        def event(t, y):
            return y[0] - 2
        event.direction = 1
        sol = solve_ivp(lambda t, y: ref.existence_4d_ode(t, y, 3.6, *args), (0, t[-1]), m.INITIAL_STATE, method='Radau', rtol=1e-10, atol=1e-13, max_step=0.25, events=event, t_eval=t)
        assert sol.success
        cache[args] = sol
    sol = cache[args]
    ev = sol.t_events[0]
    ev = ev[ev >= t[-1] / 2]
    np.testing.assert_allclose(ev, dg['poincare_upcrossings_in_second_half'], rtol=0, atol=1e-05)
    assert dg['cycle_observed'] == (len(ev) >= 2)
    err = np.max(abs(sol.y - y))
    assert err < 0.0001
    if len(ev) >= 2:
        np.testing.assert_allclose(np.diff(ev)[-1], dg['observed_period'], rtol=0, atol=1e-05)
    else:
        assert dg['observed_period'] is None
    print(f.name[10:18], h, c['preset'], args, t[-1], dg['observed_period'], dg['final_state_norm'], err, 'bounds', y.min(axis=1), y.max(axis=1), flush=True)
