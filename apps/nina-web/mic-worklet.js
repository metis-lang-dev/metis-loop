// pcm16k — AudioWorkletProcessor: mono float input at the context rate →
// low-pass → resample to 16 kHz → s16le → 20 ms frames (320 samples = 640
// bytes) posted to the main thread, which forwards them on /ws_mic.
//
// The low-pass is a windowed-sinc FIR with its cutoff just under the new
// Nyquist (8 kHz); the resampler then reads the filtered signal at fractional
// positions (linear interpolation) — correct for 44.1 k, 48 k or 96 k inputs.
// nina_splat used createScriptProcessor + sample dropping (aliasing); this
// replaces it (HARNESS.md §5).
class Pcm16k extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const inRate = (options.processorOptions && options.processorOptions.inRate) || sampleRate;
    this.ratio = inRate / 16000;
    // FIR: 63 taps, Hamming window, cutoff 7.2 kHz
    const taps = 63, fc = 7200 / inRate, mid = (taps - 1) / 2;
    this.h = new Float32Array(taps);
    let sum = 0;
    for (let i = 0; i < taps; i++) {
      const n = i - mid;
      const sinc = n === 0 ? 2 * fc : Math.sin(2 * Math.PI * fc * n) / (Math.PI * n);
      const w = 0.54 - 0.46 * Math.cos((2 * Math.PI * i) / (taps - 1));
      this.h[i] = sinc * w;
      sum += this.h[i];
    }
    for (let i = 0; i < taps; i++) this.h[i] /= sum;
    this.hist = new Float32Array(taps - 1);   // filter memory
    this.filt = new Float32Array(0);          // filtered samples awaiting resampling
    this.pos = 0;                             // fractional read position into filt
    this.out = new Int16Array(320);
    this.n = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    // filter this block (with the history of the previous one)
    const taps = this.h.length, L = taps - 1;
    const x = new Float32Array(L + ch.length);
    x.set(this.hist, 0);
    x.set(ch, L);
    const y = new Float32Array(ch.length);
    for (let i = 0; i < ch.length; i++) {
      let acc = 0;
      for (let k = 0; k < taps; k++) acc += this.h[k] * x[i + L - k];
      y[i] = acc;
    }
    this.hist.set(x.subarray(x.length - L));
    // append to the resampling buffer
    const merged = new Float32Array(this.filt.length + y.length);
    merged.set(this.filt, 0);
    merged.set(y, this.filt.length);
    this.filt = merged;
    // resample: read at pos, pos += ratio
    while (this.pos + 1 < this.filt.length) {
      const i = Math.floor(this.pos), f = this.pos - i;
      const v = this.filt[i] * (1 - f) + this.filt[i + 1] * f;
      this.out[this.n++] = Math.max(-32768, Math.min(32767, Math.round(v * 32767)));
      this.pos += this.ratio;
      if (this.n === 320) {
        this.port.postMessage(this.out.buffer.slice(0));
        this.n = 0;
      }
    }
    // drop consumed samples, keep the fractional tail
    const keep = Math.floor(this.pos);
    this.filt = this.filt.slice(keep);
    this.pos -= keep;
    return true;
  }
}
registerProcessor('pcm16k', Pcm16k);
