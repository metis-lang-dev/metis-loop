"""Hands-on validation: a weight PORT bound to live Python state,
priced through the exact evaluator, env flip re-prices, overlay
(notch-style) overrides the base. The plugin-interface kernel face."""
from metis.lang import load_llp, weight_policy
from metis.fw.registry import Registry
from metis.kernel import ForwardProjection

SRC = """catalog sensor 1.
provenance text "a hazard priced by a port reading the gap class" "2026-10-09".
layers (dyn).
stages (tick).
namespace sx produce (dyn).
pred ck : sx.
pred gclose : sx.
pred crash : sx.
pred ok : sx.
weight rss reads {gclose}.
stage tick {
  %% "the hazard fires with the rss-priced probability"
  hit [dyn] : ck * $gclose -o crash  @w rss.
  %% "the tick passes clean"
  pass [dyn] : ck -o ok  @w ~rss.
}
"""
open("sensor.llp", "w").write(SRC)
doc = load_llp("sensor.llp")
cat = doc.catalog

# --- the ENV the plugin would own: continuous state behind the port
env = {"gap_m": 18.0}          # real-valued, lives in Python

def rss(args, counts):
    # pure given (declared reads, env): the plugin contract
    close = counts.get("gclose", 0) > 0
    g = env["gap_m"]
    return 0.9 if (close and g < 10) else (0.3 if close else 0.01)

reg = Registry().weight("rss", rss)

def p_crash():
    prog = cat.ground({"ck": 1, "gclose": 1})
    pol = weight_policy(prog, doc.ports, reg.weight_bindings())
    pr = ForwardProjection(prog, 2, policy=pol)
    return sum(p for s, p in pr.final.items() if "crash" in str(s))

print("gap 18m  -> P[crash] =", p_crash())
env["gap_m"] = 6.0
print("gap  6m  -> P[crash] =", p_crash())

# --- notch-style overlay: fitted table overrides the base
reg.overlay("rss", lambda args, counts: 0.42)
print("overlay  -> P[crash] =", p_crash())
reg.pop_overlay("rss")
print("popped   -> P[crash] =", p_crash())

# --- the contract has teeth: a binding may only read its declared scope
bad_doc_src = SRC.replace("reads {gclose}", "reads {}")
open("sensor_bad.llp", "w").write(bad_doc_src)
from metis.lang.compiler import factor_hooks
doc2 = load_llp("sensor_bad.llp")
try:
    prog2 = doc2.catalog.ground({"ck": 1, "gclose": 1})
    factor_hooks(prog2, doc2.ports, reg.weight_bindings(), doc2.catalog.horn_db())
    print("scope: NOT enforced (!)")
except Exception as e:
    print("scope enforced at factoring:", str(e)[:70])
