// The tool sets by mode (loop-prompt s-3591d53b, docs/PROMPT.md §3). pi declares the tools of both loops in one
// process; each extension registers only its mode's, read once at registration from METIS_LOOP_TOOLS (loop.sh sets
// it: seed with --seed or a DIR without a bundle, workspace otherwise):
//   workspace   the surprise loop: metis-workspace's tools and catalog_edit (metis-repl), nothing of metis-domain
//   seed        the standalone catalog loop: metis-repl's and metis-domain's tools, none of metis-workspace's
//   unset/all   every tool (the tests, a hand-started pi)
// (METIS_LOOP_MODE is another variable: tui | rpc, the lock's mode.)

export type ToolSet = "workspace" | "seed" | "all";

export function toolset(env: NodeJS.ProcessEnv = process.env): ToolSet {
	const v = (env.METIS_LOOP_TOOLS || "").trim();
	if (v === "" || v === "all") return "all";
	if (v === "workspace" || v === "seed") return v;
	console.error(`METIS_LOOP_TOOLS=${v}: workspace | seed | all; every tool is registered`);
	return "all";
}

/** pi as an extension sees it, with registerTool keeping only the tools `keep` names (every other call as it is). */
export function scoped<T extends object>(pi: T, keep: (name: string) => boolean): T {
	return new Proxy(pi, {
		get(t, k, rcv) {
			if (k === "registerTool") return (def: any) => (keep(String(def?.name)) ? (t as any).registerTool(def) : undefined);
			const v = Reflect.get(t, k, rcv);
			return typeof v === "function" ? v.bind(t) : v;
		},
	});
}
