/* The release universe: every family of OpenAI's mathematics release as a small
   map of its own, set in its discipline's sector of one wheel, the citations
   between families woven through the middle; a family opens into its own map,
   and a result into its plate and panel.

   Ported from Will Cook's ai_workflow at commit 4b1ebab611 (copied and adapted;
   nothing is imported across repositories):
   - Loom, the fibre geometry of the system map:
     sites/microcosm/assets/system-map.js, l.80-117 and l.237-623 (helpers,
     resample and pointAt, polar curves, bundle, taper, fibreStroke and its
     edge cutting), copied verbatim below; the weave is left out.
   - The camera, flight path, zoom about the pointer with page-scroll handoff,
     name plates placed in the least covered of six spots, the way round words
     (shortestWay), the drill trail with exact Back, #o= deep links, reduced
     motion and the Oklab colour mixing of the Plectis universe map:
     tools/meta/dissemination/maths_site_assets/universe.js (mount l.288,
     cameraTo l.1607, flightPath l.1661, namePlate l.3133, shortestWay l.4028,
     zoomAt l.7323, the wheel handler l.7230, stepBack l.5998).
   - Focus tiers by hop distance from Zenith's universalGraphDistanceTier.ts
     (system/server/ui/src/components/graph/).
   - The rules of sites/microcosm/SOURCE_CONTRACT.md ("Map data contracts",
     "Universe map"): data apart from geometry under one generation id; labels
     never cover marks; a click selects and never leaves the page; Esc retraces
     the trail; colour belongs to evidence; one flat ground.
   Plectis meanings (Comparator and Palomar, the eight problems) are left out.
   No libraries. */
(function () {
  'use strict';

  var Loom = (function () {
    'use strict';
    /* ---- Small helpers ------------------------------------------------------ */
    var TAU = Math.PI * 2;
    function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
    function norm(a) { a %= TAU; return a < 0 ? a + TAU : a; }
    // The signed shorter turn from angle a to angle b.
    function turn(a, b) { var d = norm(b - a); return d > Math.PI ? d - TAU : d; }
    function circMean(angles, weights) {
      var x = 0, y = 0;
      for (var i = 0; i < angles.length; i++) {
        var w = weights ? weights[i] : 1;
        x += w * Math.cos(angles[i]);
        y += w * Math.sin(angles[i]);
      }
      return Math.sqrt(x * x + y * y) < 1e-9 ? (angles.length ? angles[0] : 0) : Math.atan2(y, x);
    }
    function smooth01(t) { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); }
    function nf(v) { return String(Math.round(v * 100) / 100); }
    function now() { return typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now(); }
    // A small deterministic generator (mulberry32), so every order is the
    // same picture on every visit.
    function rng(seed) {
      var s = seed >>> 0;
      return function () {
        s = (s + 0x6D2B79F5) >>> 0;
        var t = s;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    }
    function polarXY(cx, cy, list) {
      var out = new Array(list.length);
      for (var i = 0; i < list.length; i++) {
        out[i] = [cx + list[i][1] * Math.cos(list[i][0]), cy + list[i][1] * Math.sin(list[i][0])];
      }
      return out;
    }

    function measure(pts) {
      var c = new Float64Array(pts.length);
      for (var i = 1; i < pts.length; i++) c[i] = c[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      return c;
    }

    /* resample(pts, step) -> { p: [[x, y], ...], len, step }
       The polyline at even spacing (the last point exact), the spacing as
       near `step` as divides the length. */
    function resample(pts, step) {
      var cum = measure(pts), len = cum[cum.length - 1];
      var k = Math.max(1, Math.round(len / step)), h = len / k, out = [pts[0].slice()], j = 1;
      for (var i = 1; i < k; i++) {
        var s = i * h;
        while (j < pts.length - 1 && cum[j] < s) j++;
        var seg = cum[j] - cum[j - 1], t = seg > 0 ? (s - cum[j - 1]) / seg : 0;
        out.push([pts[j - 1][0] + (pts[j][0] - pts[j - 1][0]) * t, pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * t]);
      }
      out.push(pts[pts.length - 1].slice());
      return { p: out, len: len, step: h };
    }

    /* pointAt(pts, s) -> { x, y, tx, ty }: the point at arc length s and the
       unit direction of travel there. */
    function pointAt(pts, s, cum) {
      cum = cum || measure(pts);
      var n = pts.length, lo = 1, hi = n - 1;
      s = clamp(s, 0, cum[n - 1]);
      while (lo < hi) { var mid = (lo + hi) >> 1; if (cum[mid] < s) lo = mid + 1; else hi = mid; }
      var a = pts[lo - 1], b = pts[lo], seg = cum[lo] - cum[lo - 1] || 1, t = (s - cum[lo - 1]) / seg;
      return { x: a[0] + (b[0] - a[0]) * t, y: a[1] + (b[1] - a[1]) * t, tx: (b[0] - a[0]) / seg, ty: (b[1] - a[1]) / seg };
    }

    /* lineD(pts) -> path data for a polyline, straight segments. */
    function lineD(pts) {
      if (!pts.length) return '';
      var d = 'M' + nf(pts[0][0]) + ' ' + nf(pts[0][1]);
      for (var i = 1; i < pts.length; i++) d += 'L' + nf(pts[i][0]) + ' ' + nf(pts[i][1]);
      return d;
    }

    /* ---- Curves in polar form -------------------------------------------------- */
    /* Every line inside the ring is shaped in polar coordinates, then set on the
       page: a curve whose control points keep their angle at an end leaves and
       lands along the radius, and a curve whose control radii all stay above r
       never comes nearer the centre than r. */

    // A cubic Bézier in polar form, sampled about every `px` pixels.
    function polarBezier(c0, c1, c2, c3, px, out, skipFirst) {
      out = out || [];
      var rm = (c0[1] + c3[1]) / 2;
      var span = Math.abs(c1[0] - c0[0]) * c0[1] + Math.abs(c2[0] - c1[0]) * rm + Math.abs(c3[0] - c2[0]) * c3[1] +
        Math.abs(c1[1] - c0[1]) + Math.abs(c2[1] - c1[1]) + Math.abs(c3[1] - c2[1]);
      var k = clamp(Math.ceil(span / (px || 3)), 3, 160);
      for (var j = skipFirst ? 1 : 0; j <= k; j++) {
        var t = j / k, u = 1 - t, b0 = u * u * u, b1 = 3 * u * u * t, b2 = 3 * u * t * t, b3 = t * t * t;
        out.push([b0 * c0[0] + b1 * c1[0] + b2 * c2[0] + b3 * c3[0], b0 * c0[1] + b1 * c1[1] + b2 * c2[1] + b3 * c3[1]]);
      }
      return out;
    }

    /* polarSpline(ctrl, beta, px) -> polar points
       A clamped uniform cubic B-spline through polar control points (angles
       unwrapped), straightened by `beta` as in Holten's hierarchical edge
       bundling: each inner control point is drawn toward the even run between
       the two ends by (1 - beta). In polar form that run is the arc at the
       ends' radius, so a weaker bundle rides nearer the rim. beta 1 keeps the
       control polygon; 0 is the plain arc. */
    function polarSpline(ctrl, beta, px) {
      var n = ctrl.length - 1, P = new Array(n + 1);
      for (var i = 0; i <= n; i++) {
        var c = ctrl[i];
        if (i === 0 || i === n || !(beta < 1)) { P[i] = c; continue; }
        var t = i / n;
        P[i] = [beta * c[0] + (1 - beta) * (ctrl[0][0] + t * (ctrl[n][0] - ctrl[0][0])),
                beta * c[1] + (1 - beta) * (ctrl[0][1] + t * (ctrl[n][1] - ctrl[0][1]))];
      }
      var Q = [P[0], P[0]].concat(P, [P[n], P[n]]), out = [];
      for (var s = 0; s + 3 < Q.length; s++) {
        var p0 = Q[s], p1 = Q[s + 1], p2 = Q[s + 2], p3 = Q[s + 3];
        var span = Math.abs(p2[0] - p1[0]) * (p1[1] + p2[1]) / 2 + Math.abs(p2[1] - p1[1]);
        var k = clamp(Math.ceil(span / (px || 3)), 1, 80);
        for (var j = s === 0 ? 0 : 1; j <= k; j++) {
          var u = j / k, u2 = u * u, u3 = u2 * u, v = 1 - u;
          var b0 = v * v * v / 6, b1 = (3 * u3 - 6 * u2 + 4) / 6, b2 = (-3 * u3 + 3 * u2 + 3 * u + 1) / 6, b3 = u3 / 6;
          out.push([b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0], b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1]]);
        }
      }
      return out;
    }

    /* ---- Fibre routes ---------------------------------------------------------- */

    /* bundle(spec) -> [{ pts, polar, local, pair, lane }] in the order of spec.links
       Radial hierarchical edge bundling for a ring of components in families.
       spec = {
         cx, cy          the ring's centre
         R               the radius the component marks sit on
         at              each component's angle
         group           each component's family index
         hub             each family's hub angle (its sector's middle)
         links           [[from, to], ...] component indices
         rimR            where a route leaves its mark              (R - 9)
         hubR            the family hubs' ring                       (0.79 R)
         lanes           [deepest, shallowest] travel radii          ([0.57 R, 0.73 R])
         beta            Holten's bundling strength                  (0.85)
         leave           how far a route runs radially first         (0.05 R)
         shape           'swoop' (default) or 'lanes' (see below)
         swoopGain       depth of a swoop per radian travelled, px   ((hubR - lanes[0]) / pi)
         fibrePitch      gap between fibres of one pair, px          (0.9)
         localGain       depth of a family's own arc per radian, x R (0.2)
         localDepth      [shallowest, deepest] family arc, px        ([7, 0.17 R])
         px              sampling step, px                           (3)
       }
       A link between families runs from its mark straight in, through its
       family's hub, the shorter way round to the other family's hub, and out
       to the far mark, never through the centre: every control point stays
       at or outside lanes[0], and the spline is drawn in polar form, so it
       cannot come nearer. 'swoop' dips from hub to hub, deepest at the middle
       and the deeper the further it travels, like nested arcs of an arc
       diagram: pairs leaving a hub the same way share their first stretch
       and then part, which is what makes a bundle read as a rope. 'lanes'
       gives each family pair its own concentric lane instead (the shortest
       stretches shallowest), for a ruled look. The fibres of one pair lie
       side by side, the one reaching widest the deepest, so they do not
       cross one another. A link inside one family is a U just inside the rim
       whose depth grows with the angle it spans; a pair of links both ways
       between two components draws as two, the second a little deeper.
       `pair` (the family-pair index, -1 for a link inside one family) is the
       natural bundle key for the weave. */
    function bundle(spec) {
      var R = spec.R, cx = spec.cx, cy = spec.cy;
      var rimR = spec.rimR || R - 9, hubR = spec.hubR || 0.79 * R;
      var lanes = spec.lanes || [0.57 * R, 0.73 * R], beta = spec.beta == null ? 0.85 : spec.beta;
      var leave = spec.leave || 0.05 * R, pitch = spec.fibrePitch == null ? 0.9 : spec.fibrePitch;
      var gain = spec.localGain == null ? 0.2 : spec.localGain, ldep = spec.localDepth || [7, 0.17 * R];
      var px = spec.px || 3, shape = spec.shape || 'swoop';
      var swoop = spec.swoopGain == null ? (hubR - lanes[0]) / Math.PI : spec.swoopGain;
      var at = spec.at, group = spec.group, hub = spec.hub, links = spec.links;
      // The pairs of families with links between them, each travelling the
      // shorter way between its hubs.
      var pairAt = Object.create(null), pairs = [];
      links.forEach(function (l, k) {
        var ga = group[l[0]], gb = group[l[1]];
        if (ga === gb) return;
        var lo = Math.min(ga, gb), hi = Math.max(ga, gb), key = lo + '-' + hi;
        if (pairAt[key] === undefined) {
          var t = turn(hub[lo], hub[hi]);
          pairAt[key] = pairs.length;
          pairs.push({ lo: lo, hi: hi, travel: t, s: t >= 0 ? norm(hub[lo]) : norm(hub[hi]), len: Math.abs(t), members: [] });
        }
        pairs[pairAt[key]].members.push(k);
      });
      // Lanes: the shortest stretches shallowest; a pair takes the shallowest
      // lane no overlapping shorter pair holds.
      function within(a, p) { var d = norm(a - p.s); return d <= p.len + 1e-6; }
      function overlaps(p, q) { return within(p.s, q) || within(q.s, p) || within(p.s + p.len, q) || within(q.s + q.len, p); }
      var byLen = pairs.slice().sort(function (p, q) { return p.len - q.len || p.lo - q.lo || p.hi - q.hi; });
      byLen.forEach(function (p, i) {
        var used = Object.create(null);
        for (var j = 0; j < i; j++) if (overlaps(p, byLen[j])) used[byLen[j].lane] = true;
        var lane = 0;
        while (used[lane]) lane++;
        p.lane = lane;
      });
      var nLanes = 1 + pairs.reduce(function (m, p) { return Math.max(m, p.lane); }, 0);
      var laneGap = nLanes > 1 ? Math.min(14, (lanes[1] - lanes[0]) / (nLanes - 1)) : 0;
      pairs.forEach(function (p) { p.r = lanes[1] - p.lane * laneGap; });
      // Fibres side by side in their band: the one reaching widest deepest.
      var offset = Object.create(null);
      pairs.forEach(function (p) {
        var reach = p.members.map(function (k) {
          var l = links[k], from = group[l[0]] === p.lo ? l[0] : l[1], to = from === l[0] ? l[1] : l[0];
          var dir = p.travel >= 0 ? 1 : -1;
          // How far outside the hubs the two ends sit, along the travel.
          var w = -dir * turn(hub[p.lo], at[from]) + dir * turn(hub[p.hi], at[to]);
          return { k: k, w: w };
        }).sort(function (x, y) { return y.w - x.w || x.k - y.k; });
        var m = reach.length;
        reach.forEach(function (x, j) { offset[x.k] = (j - (m - 1) / 2) * pitch; });
      });
      return links.map(function (l, k) {
        var a = l[0], b = l[1], ga = group[a], gb = group[b];
        if (ga === gb) {
          var sw = turn(at[a], at[b]);
          // Both directions of a pair of links stay visible: the second a
          // little deeper.
          var twin = 0;
          for (var j = 0; j < k; j++) if (links[j][0] === b && links[j][1] === a) twin = 1;
          var h = clamp(gain * Math.abs(sw) * R, ldep[0], ldep[1]) + twin * 2.2;
          var e = 4 / 3 * h;
          var pol = polarBezier([at[a], rimR], [at[a], rimR - e], [at[a] + sw, rimR - e], [at[a] + sw, rimR], px);
          return { pts: polarXY(cx, cy, pol), polar: pol, local: true, pair: -1, lane: -1 };
        }
        var p = pairs[pairAt[Math.min(ga, gb) + '-' + Math.max(ga, gb)]];
        var dir = ga === p.lo ? (p.travel >= 0 ? 1 : -1) : (p.travel >= 0 ? -1 : 1);
        var hA = hub[ga], travel = ga === p.lo ? p.travel : -p.travel;
        var A0 = hA + turn(hA, at[a]), hB = hA + travel, B1 = hB + turn(hub[gb], at[b]);
        var ctrl = [[A0, rimR], [A0, rimR - leave], [hA, hubR]];
        if (shape === 'lanes') {
          // Concentric lanes: the pair's own ring, entered and left near the hubs.
          var rl = p.r + offset[k];
          var lead = Math.min(0.09, Math.abs(travel) * 0.18) * dir;
          var span = travel - 2 * lead, steps = Math.max(1, Math.ceil(Math.abs(span) / 0.32));
          for (var s = 0; s <= steps; s++) ctrl.push([hA + lead + span * s / steps, rl]);
        } else {
          // A swoop: down from the hub and back up to the other, deepest at
          // the middle and deeper the further it travels, like nested arcs of
          // an arc diagram; pairs that leave a hub the same way share their
          // first stretch, then part.
          var depth = Math.min(hubR - lanes[0], swoop * Math.abs(travel)) + offset[k];
          [0.2, 0.4, 0.5, 0.6, 0.8].forEach(function (t) {
            ctrl.push([hA + travel * t, hubR - depth * Math.sin(Math.PI * t)]);
          });
        }
        ctrl.push([hB, hubR], [B1, rimR - leave], [B1, rimR]);
        var pol2 = polarSpline(ctrl, beta, px);
        return { pts: polarXY(cx, cy, pol2), polar: pol2, local: false, pair: pairs.indexOf(p), lane: p.lane };
      });
    }

    /* taper(profile) -> function (s, len) -> width in px
       profile = {
         start   width where the fibre leaves its component   (0.3)
         body    width in the bundle                          (1.3)
         end     width where it reaches the far component     (0.65)
         rise    px over which it grows from start to body    (34)
         fall    px over which it narrows to its end          (26)
         swell   extra fraction of body at the middle         (0.18)
       }
       Thin where it leaves, fuller in the bundle, parting at the far end; the
       two ends differ, so the drawing carries direction without arrowheads. */
    function taper(p) {
      p = p || {};
      var w0 = p.start == null ? 0.3 : p.start, wb = p.body == null ? 1.3 : p.body, w1 = p.end == null ? 0.65 : p.end;
      var rise = p.rise || 34, fall = p.fall || 26, swell = p.swell == null ? 0.18 : p.swell;
      return function (s, len) {
        var r = Math.min(rise, 0.42 * len), f = Math.min(fall, 0.4 * len);
        var w = wb + (w0 - wb) * (1 - smooth01(s / r)) + (w1 - wb) * (1 - smooth01((len - s) / f));
        var t = len > 0 ? s / len : 0, bump = Math.sin(Math.PI * t);
        return Math.max(0.08, w + wb * swell * bump * bump);
      };
    }

    /* fibreStroke(pts, opts) -> path data: the route as filled outlines
       pts     the route's centre line (a polyline)
       opts = {
         width     a number, or function (s, len) -> px (see taper)
         cuts      the gaps from weave(), for this route   ([])
         step      sampling step along the route, px        (2.2)
         minPiece  shortest piece kept between two gaps, px (2.4)
       }
       Fill it, never stroke it. Each gap from the weave is cut parallel to the
       line passing over, at a constant clearance from it, so the ends of the
       line beneath are clean and the gap reads as the same width at every
       angle. Pieces left shorter than minPiece are dropped rather than drawn
       as specks. */
    function fibreStroke(pts, opts) {
      opts = opts || {};
      if (!pts || pts.length < 2) return '';
      var rs = resample(pts, opts.step || 2.2), P = rs.p, n = P.length, len = rs.len, h = rs.step;
      var wf = typeof opts.width === 'function' ? opts.width : (function (c) { return function () { return c; }; })(opts.width || 1);
      var Lx = new Float64Array(n), Ly = new Float64Array(n), Rx = new Float64Array(n), Ry = new Float64Array(n);
      for (var i = 0; i < n; i++) {
        var a = P[Math.max(0, i - 1)], b = P[Math.min(n - 1, i + 1)];
        var tx = b[0] - a[0], ty = b[1] - a[1], tl = Math.hypot(tx, ty) || 1;
        var nx = -ty / tl, ny = tx / tl, w = wf(i * h, len) / 2;
        Lx[i] = P[i][0] + nx * w; Ly[i] = P[i][1] + ny * w;
        Rx[i] = P[i][0] - nx * w; Ry[i] = P[i][1] - ny * w;
      }
      var gaps = edgeGaps(opts.cuts || [], P, h, Lx, Ly, Rx, Ry, wf, len);
      var minPiece = (opts.minPiece == null ? 2.4 : opts.minPiece) / h;
      // The pieces between the gaps, on both edges at once.
      var pieces = [], fromL = 0, fromR = 0;
      gaps.forEach(function (g) {
        pieces.push([fromL, g.inL, fromR, g.inR]);
        fromL = g.outL; fromR = g.outR;
      });
      pieces.push([fromL, n - 1, fromR, n - 1]);
      var keepL = edgeKeep(Lx, Ly, 0.1), keepR = edgeKeep(Rx, Ry, 0.1);
      var d = '';
      pieces.forEach(function (pc) {
        if (pc[1] - pc[0] < minPiece || pc[3] - pc[2] < minPiece) return;
        d += 'M' + edgeRun(Lx, Ly, pc[0], pc[1], false, keepL) + 'L' + edgeRun(Rx, Ry, pc[2], pc[3], true, keepR) + 'Z';
      });
      return d;
    }
    /* The samples of an edge worth writing: where the edge runs straight to
       within `tol` px, the samples between the ends of the run add nothing
       to the picture and only lengthen the path the browser parses and
       fills. A sample is kept wherever leaving it out would move any sample
       since the last one kept further than tol from the chord. */
    function edgeKeep(X, Y, tol) {
      var n = X.length, keep = new Uint8Array(n);
      if (n < 3) { keep.fill(1); return keep; }
      keep[0] = 1; keep[n - 1] = 1;
      var a = 0;
      for (var i = 2; i < n; i++) {
        var dx = X[i] - X[a], dy = Y[i] - Y[a], L = Math.sqrt(dx * dx + dy * dy);
        if (i - a > 48) { keep[i - 1] = 1; a = i - 1; continue; }
        if (L < 1e-9) continue;
        for (var j = a + 1; j < i; j++) {
          if (Math.abs((X[j] - X[a]) * dy - (Y[j] - Y[a]) * dx) / L > tol) { keep[i - 1] = 1; a = i - 1; break; }
        }
      }
      return keep;
    }
    /* coarse(pts, tol) -> the same polyline with the points that lie within
       tol px of a straight run left out, kept on the array so it is made
       once. The weave finds its crossings on these: a crossing moves by
       well under half a pixel, and the search, which tests segments
       against segments, has a fifth as many to test. */
    function coarse(pts, tol) {
      if (pts.__coarse) return pts.__coarse;
      var n = pts.length;
      if (n < 4) return (pts.__coarse = pts);
      var X = new Float64Array(n), Y = new Float64Array(n);
      for (var i = 0; i < n; i++) { X[i] = pts[i][0]; Y[i] = pts[i][1]; }
      var keep = edgeKeep(X, Y, tol || 0.15), out = [];
      for (var k = 0; k < n; k++) if (keep[k]) out.push(pts[k]);
      try { Object.defineProperty(pts, '__coarse', { value: out, enumerable: false }); } catch (e) {}
      return out;
    }
    // The points of one edge between two fractional sample indices, as
    // "x y L x y ..." (reversed if asked), the samples between kept ones
    // left out.
    function edgeRun(X, Y, from, to, reverse, keep) {
      var list = [];
      function at(f) { var i = Math.min(X.length - 2, Math.floor(f)), t = f - i; return nf(X[i] + (X[i + 1] - X[i]) * t) + ' ' + nf(Y[i] + (Y[i + 1] - Y[i]) * t); }
      list.push(at(from));
      for (var i = Math.floor(from) + 1; i < to; i++) if (!keep || keep[i]) list.push(nf(X[i]) + ' ' + nf(Y[i]));
      list.push(at(Math.min(to, X.length - 1)));
      if (reverse) list.reverse();
      return list.join('L');
    }
    // Where each edge of an outline enters and leaves the clear band either
    // side of the line passing over, merged where two gaps meet.
    function edgeGaps(cuts, P, h, Lx, Ly, Rx, Ry, wf, len) {
      var n = P.length, out = [];
      cuts.slice().sort(function (p, q) { return p.s - q.s; }).forEach(function (c) {
        var ic = c.s / h, wu = wf(c.s, len);
        var sin = Math.max(0.2, c.sin || 1), reach = (c.h + wu) / sin + 3 * h;
        var lo = Math.max(0, Math.floor(ic - reach / h)), hi = Math.min(n - 1, Math.ceil(ic + reach / h));
        var gl = band(Lx, Ly, c, lo, hi, ic), gr = band(Rx, Ry, c, lo, hi, ic);
        if (!gl || !gr) {
          // The edge never meets the over line near here (a very short or
          // very wide piece): cut square instead.
          var half = (c.h + wu / 2 * Math.abs(c.cos || 0)) / sin / h;
          gl = gr = [Math.max(0, ic - half), Math.min(n - 1, ic + half)];
        }
        out.push({ inL: gl[0], outL: gl[1], inR: gr[0], outR: gr[1] });
      });
      // Merge overlapping gaps.
      var merged = [];
      out.forEach(function (g) {
        var m = merged[merged.length - 1];
        if (m && (g.inL <= m.outL || g.inR <= m.outR)) {
          m.outL = Math.max(m.outL, g.outL); m.outR = Math.max(m.outR, g.outR);
          m.inL = Math.min(m.inL, g.inL); m.inR = Math.min(m.inR, g.inR);
        } else merged.push(g);
      });
      return merged;
    }
    // On one edge, the stretch around sample ic whose signed distance from the
    // over line is under the clearance.
    function band(X, Y, c, lo, hi, ic) {
      function dist(i) { return (X[i] - c.x) * c.nx + (Y[i] - c.y) * c.ny; }
      // The sign change nearest the crossing.
      var best = -1, bd = Infinity;
      for (var i = lo; i < hi; i++) {
        var d0 = dist(i), d1 = dist(i + 1);
        if ((d0 <= 0 && d1 >= 0) || (d0 >= 0 && d1 <= 0)) { var dd = Math.abs(i + 0.5 - ic); if (dd < bd) { bd = dd; best = i; } }
      }
      if (best < 0) return null;
      var H = c.h, k = best, entry, exit;
      while (k >= lo && Math.abs(dist(k)) < H) k--;
      if (k < lo) entry = lo;
      else { var a = dist(k), b = dist(k + 1), tgt = a > 0 ? H : -H; entry = k + (a - tgt) / ((a - b) || 1); }
      k = best + 1;
      while (k <= hi && Math.abs(dist(k)) < H) k++;
      if (k > hi) exit = hi;
      else { var a2 = dist(k - 1), b2 = dist(k), tgt2 = b2 > 0 ? H : -H; exit = k - 1 + (a2 - tgt2) / ((a2 - b2) || 1); }
      return [clamp(entry, 0, X.length - 1), clamp(exit, 0, X.length - 1)];
    }


    return {
      bundle: bundle, taper: taper, fibreStroke: fibreStroke, polarXY: polarXY, polarBezier: polarBezier,
      measure: measure, resample: resample, pointAt: pointAt, turn: turn, norm: norm, circMean: circMean
    };
  })();

  /* ---- Small helpers --------------------------------------------------- */
  var TAU = Math.PI * 2;
  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function smooth(t) { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); }
  function easeInOut(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  // One date format across the site: "8 October 2026".
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  function longDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
    return m ? (+m[3]) + ' ' + MONTHS[+m[2] - 1] + ' ' + m[1] : String(iso || '');
  }
  function fmtNum(n) { return typeof n === 'number' ? n.toLocaleString('en-GB') : String(n); }
  function fill(template, vars) {
    return String(template).replace(/\{(\w+)\}/g, function (m, k) {
      return vars && vars[k] != null ? fmtNum(vars[k]) : m;
    });
  }
  function boxesMeet(a, b, grace) {
    grace = grace || 0;
    return a.x0 < b.x1 - grace && a.x1 > b.x0 + grace && a.y0 < b.y1 - grace && a.y1 > b.y0 + grace;
  }
  function overlap(a, b) {
    var dx = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), dy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
    return dx > 0 && dy > 0 ? dx * dy : 0;
  }

  /* ---- Colour, mixed in Oklab (from the Plectis universe map) ----------- */
  var parsedColors = {};
  function parseColor(text) {
    var key = String(text == null ? '' : text).trim();
    if (Object.prototype.hasOwnProperty.call(parsedColors, key)) return parsedColors[key];
    var out = null, m;
    if ((m = /^#([0-9a-f]{3,8})$/i.exec(key))) {
      var hex = m[1];
      if (hex.length === 3 || hex.length === 4) hex = hex.replace(/(.)/g, '$1$1');
      if (hex.length === 6 || hex.length === 8) {
        out = [parseInt(hex.slice(0, 2), 16) / 255, parseInt(hex.slice(2, 4), 16) / 255,
               parseInt(hex.slice(4, 6), 16) / 255, hex.length === 8 ? parseInt(hex.slice(6, 8), 16) / 255 : 1];
      }
    } else if ((m = /^rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)(?:[\s,/]+([\d.]+%?))?\s*\)$/i.exec(key))) {
      var channel = function (v) { return /%$/.test(v) ? parseFloat(v) / 100 : parseFloat(v) / 255; };
      out = [channel(m[1]), channel(m[2]), channel(m[3]),
             m[4] == null ? 1 : /%$/.test(m[4]) ? parseFloat(m[4]) / 100 : parseFloat(m[4])];
    }
    if (out && !out.every(function (v) { return isFinite(v); })) out = null;
    parsedColors[key] = out;
    return out;
  }
  function toLinear(c) { return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
  function toGamma(c) { return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055; }
  function rgbToOklab(c) {
    var r = toLinear(c[0]), g = toLinear(c[1]), b = toLinear(c[2]);
    var l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    var m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    var s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    return [0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s];
  }
  function oklabToRgb(c) {
    var l = c[0] + 0.3963377774 * c[1] + 0.2158037573 * c[2];
    var m = c[0] - 0.1055613458 * c[1] - 0.0638541728 * c[2];
    var s = c[0] - 0.0894841775 * c[1] - 1.2914855480 * c[2];
    l = l * l * l; m = m * m * m; s = s * s * s;
    return [toGamma(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
            toGamma(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
            toGamma(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)];
  }
  function rgbText(c) {
    var v = function (x) { return Math.round(Math.max(0, Math.min(1, x)) * 255); };
    return 'rgb(' + v(c[0]) + ', ' + v(c[1]) + ', ' + v(c[2]) + ')';
  }
  function overGround(c, ground) {
    if (c[3] >= 0.999) return c;
    return [c[0] * c[3] + ground[0] * (1 - c[3]), c[1] * c[3] + ground[1] * (1 - c[3]),
            c[2] * c[3] + ground[2] * (1 - c[3]), 1];
  }
  // color-mix(in oklab, a, b t): t of the way from a to b.
  function mixOklab(a, b, t, ground) {
    var ca = parseColor(a), cb = parseColor(b);
    if (!ca || !cb) return a;
    if (ground) { ca = overGround(ca, ground); cb = overGround(cb, ground); }
    var la = rgbToOklab(ca), lb = rgbToOklab(cb);
    return rgbText(oklabToRgb([la[0] + (lb[0] - la[0]) * t, la[1] + (lb[1] - la[1]) * t, la[2] + (lb[2] - la[2]) * t]));
  }

  /* ---- KaTeX macros: the same set the site's pages use (assets/atlas.js) -- */
  var GLOBAL_MACROS = {
    '\\ensuremath': '#1', '\\xspace': '', '\\bm': '\\boldsymbol{#1}', '\\mathbbm': '\\mathbb{#1}',
    '\\textup': '\\textrm{#1}', '\\textsc': '\\textrm{#1}', '\\upshape': '', '\\eqref': '\\text{(#1)}',
    '\\label': '', '\\nobreak': '', '\\allowbreak': '', '\\hbox': '\\text{#1}', '\\mbox': '\\text{#1}',
    '\\dfrac': '\\frac{#1}{#2}', '\\RR': '\\mathbb{R}', '\\NN': '\\mathbb{N}', '\\ZZ': '\\mathbb{Z}',
    '\\QQ': '\\mathbb{Q}', '\\CC': '\\mathbb{C}',
    '\\norm': '\\left\\lVert #1\\right\\rVert', '\\abs': '\\left\\lvert #1\\right\\rvert',
    '\\ip': '\\left\\langle #1\\right\\rangle', '\\floor': '\\left\\lfloor #1\\right\\rfloor',
    '\\ceil': '\\left\\lceil #1\\right\\rceil', '\\set': '\\left\\{ #1\\right\\}'
  };

  // The drawing's type is the page's: the families named by atlas.css's tokens.
  var SANS = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
  var SERIF = 'Georgia, "Times New Roman", serif';
  var MONO = 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace';
  function readFonts() {
    var cs = getComputedStyle(document.documentElement);
    var pick = function (name, fb) { var v = cs.getPropertyValue(name).trim(); return v || fb; };
    SANS = pick('--sans', SANS); SERIF = pick('--serif', SERIF); MONO = pick('--mono', MONO);
  }
  readFonts();

  function mount(root) {
    var canvas = root.querySelector('[data-u-canvas]');
    var stage = root.querySelector('[data-u-stage]');
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext('2d');
    var COPY = {};
    try { COPY = JSON.parse(document.getElementById('universe-copy').textContent); } catch (e) { COPY = {}; }
    function T(path, vars) {
      var node = COPY;
      path.split('.').forEach(function (p) { node = node && node[p]; });
      if (typeof node !== 'string') return path;
      return vars ? fill(node, vars) : node;
    }
    function count(key, n) { return n === 1 && COPY.counts[key + '_one'] ? T('counts.' + key + '_one') : T('counts.' + key, { n: n }); }

    var panelBody = root.querySelector('[data-u-scroll]');
    var viewEl = root.querySelector('[data-u-view]');
    var trailEl = root.querySelector('[data-u-trail]');
    var titleEl = root.querySelector('#u-title');
    var legendBody = root.querySelector('[data-u-legend-body]');
    var listSec = root.querySelector('.u-listsec');
    var resultsEl = root.querySelector('[data-u-results]');
    var searchIn = root.querySelector('[data-u-search]');
    var statusEl = root.querySelector('[data-u-status]');
    var liveEl = root.querySelector('[data-u-live]');
    var helpEl = root.querySelector('[data-u-help]');
    var toolsEl = root.querySelector('.u-tools');
    var restViewHtml = viewEl ? viewEl.innerHTML : '';

    var reduceQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
    var reduceMotion = !!(reduceQuery && reduceQuery.matches);
    if (reduceQuery && reduceQuery.addEventListener) reduceQuery.addEventListener('change', function () { reduceMotion = reduceQuery.matches; });

    /* ---- State ------------------------------------------------------------ */
    var D = null, L = null;           // data and layout
    var fams = [], objects = [], byKey = {};
    var view = { k: 1, tx: 0, ty: 0 }, fitK = 1, viewFitted = true;
    var W = 0, H = 0, dpr = 1;
    var sel = null;                   // selected object key
    var hover = null;                 // hovered object key
    var trail = [];                   // [{ key, before }]
    var cameraFrame = 0, cameraGoal = null, moving = false;
    var palette = {};
    var query = '', matches = null, matchFam = null, searchRows = null, searchLoading = null;
    var shards = {}, shardLoading = {};
    var hitTargets = [];              // labels that can be clicked: { box, key }
    var drawPending = false;
    var lastPlan = null;

    /* ---- Text ------------------------------------------------------------ */
    var widthCache = {};
    function textWidth(text, font) {
      var key = font + '|' + text;
      var w = widthCache[key];
      if (w === undefined) {
        ctx.font = font;
        w = widthCache[key] = ctx.measureText(text).width;
      }
      return w;
    }
    // The text in exactly n lines, breaking only between words, the longest line as short as it can be.
    function balancedLines(text, n, font) {
      var words = String(text).split(' ').filter(Boolean);
      if (n <= 1 || words.length < 2) return { lines: [words.join(' ')], width: textWidth(words.join(' '), font) };
      n = Math.min(n, words.length);
      var space = textWidth(' ', font), ww = words.map(function (w) { return textWidth(w, font); });
      var span = function (i, j) { var s = 0; for (var q = i; q < j; q++) s += ww[q]; return s + space * (j - i - 1); };
      var m = words.length, best = [], cut = [];
      for (var i = 0; i <= m; i++) { best.push([]); cut.push([]); }
      for (var j = 1; j <= m; j++) { best[1][j] = span(0, j); cut[1][j] = 0; }
      for (var lines = 2; lines <= n; lines++) {
        for (var j2 = lines; j2 <= m; j2++) {
          var b = Infinity, at = lines - 1;
          for (var i2 = lines - 1; i2 < j2; i2++) {
            var v = Math.max(best[lines - 1][i2], span(i2, j2));
            if (v < b - 1e-6) { b = v; at = i2; }
          }
          best[lines][j2] = b; cut[lines][j2] = at;
        }
      }
      var out = [], end = m;
      for (var l2 = n; l2 >= 1; l2--) {
        var st = l2 === 1 ? 0 : cut[l2][end];
        out.unshift(words.slice(st, end).join(' '));
        end = st;
      }
      return { lines: out, width: best[n][m] };
    }
    // The fewest whole lines (up to max) that hold the text within maxW; null when none does.
    function fitLines(text, font, maxW, max) {
      for (var n = 1; n <= max; n++) {
        var b = balancedLines(text, n, font);
        if (b.width <= maxW) return b;
        if (b.lines.length < n) break;
      }
      return null;
    }

    /* ---- Palette from the stylesheet's tokens ------------------------------ */
    function readPalette() {
      var cs = getComputedStyle(root);
      var get = function (name, fb) { var v = cs.getPropertyValue(name).trim(); return v || fb; };
      var p = {
        ground: get('--u-ground', '#1c1526'), ink: get('--u-ink', '#f2e6d4'), muted: get('--u-muted', '#bcb8c6'),
        faint: get('--u-faint', '#a6a2b1'), struct: get('--u-struct', '#6f6878'), structSoft: get('--u-struct-soft', '#4a4453'),
        cloud: get('--u-cloud', 'rgba(242,230,212,0.05)'), slice: get('--u-slice', 'rgba(242,230,212,0.06)'),
        fibre: get('--u-fibre', 'rgba(242,230,212,0.24)'), cites: get('--u-cites', '#e18a79'), cited: get('--u-cited', '#97c1df'),
        steel: get('--u-steel', '#97c1df'), brick: get('--u-brick', '#e18a79'), paired: get('--u-paired', '#7ea6c6'),
        plate: get('--u-plate', '#272132'), plateRule: get('--u-plate-rule', '#484251'), focus: get('--u-focus', '#f2e6d4')
      };
      var groundRGB = parseColor(p.ground) || [0, 0, 0, 1];
      // Lean statements by how many outside groups accepted their re-run: the
      // steel ink in four steps of lightness toward the ground, so the strongest
      // evidence is the strongest mark in either theme.
      p.lean = [null, mixOklab(p.steel, p.ground, 0.62, groundRGB), mixOklab(p.steel, p.ground, 0.3, groundRGB), p.steel];
      p.structFaint = mixOklab(p.struct, p.ground, 0.45, groundRGB);
      p.groundRGB = groundRGB;
      palette = p;
    }

    /* ---- Data ------------------------------------------------------------ */
    function fetchJson(url) {
      return fetch(url, { credentials: 'same-origin' }).then(function (r) {
        if (!r.ok) throw new Error(url + ': ' + r.status);
        return r.json();
      });
    }
    function validate(data, layout) {
      var gen = root.getAttribute('data-generation');
      if (!data || !layout || data.generation_id !== layout.generation_id || (gen && data.generation_id !== gen)) {
        throw new Error('the data and the layout come from different builds');
      }
      var finite = function (v) { return typeof v === 'number' && isFinite(v); };
      if (layout.families.length !== data.families.length || layout.results.length !== data.results.length ||
          layout.lean.length !== data.lean.length || layout.papers.length !== data.papers.length) {
        throw new Error('the layout does not place every object');
      }
      layout.families.forEach(function (f) { if (!f.every(finite)) throw new Error('a family has no finite place'); });
      layout.results.forEach(function (p) { if (!p.every(finite)) throw new Error('a result has no finite place'); });
      layout.lean.forEach(function (p) { if (!p.every(finite)) throw new Error('a Lean statement has no finite place'); });
    }
    function ingest(data, layout) {
      D = data; L = layout;
      var addObj = function (key, kind, idx) {
        if (byKey[key] !== undefined) throw new Error('duplicate id ' + key);
        byKey[key] = objects.length;
        objects.push({ key: key, kind: kind, i: idx });
      };
      D.disciplines.forEach(function (d, i) { addObj(d.id, 'd', i); });
      D.families.forEach(function (f, i) {
        addObj(f.id, 'f', i);
        var g = L.families[i];
        fams.push({ x: g[0], y: g[1], r: g[2], a: g[3], d: f.d, data: f, hop: {} });
      });
      D.papers.forEach(function (p, i) { addObj(p.id, 'p', i); });
      D.results.forEach(function (r, i) { addObj(r.id, 'r', i); });
      D.lean.forEach(function (l, i) { addObj(l.id, 'l', i); });
      // Neighbours for the focus tiers (one hop through a citation).
      D.links.forEach(function (row) {
        fams[row[0]].hop[row[1]] = 1;
        fams[row[1]].hop[row[0]] = 1;
      });
      buildFibres();
    }
    function obj(key) { var i = byKey[key]; return i === undefined ? null : objects[i]; }
    function famOf(o) {
      if (!o) return -1;
      if (o.kind === 'f') return o.i;
      if (o.kind === 'p') return D.papers[o.i].f;
      if (o.kind === 'r') return D.results[o.i].f;
      if (o.kind === 'l') return D.lean[o.i].f;
      return -1;
    }
    function discOf(o) {
      if (!o) return -1;
      if (o.kind === 'd') return o.i;
      var f = famOf(o);
      return f >= 0 ? fams[f].d : -1;
    }
    function nameOf(o) {
      if (!o) return '';
      if (o.kind === 'd') return D.disciplines[o.i].name;
      if (o.kind === 'f') return D.families[o.i].title;
      if (o.kind === 'p') return D.papers[o.i].title;
      if (o.kind === 'r') { var r = D.results[o.i]; return resultName(r) + (r.title ? ' (' + r.title + ')' : ''); }
      if (o.kind === 'l') return D.lean[o.i].name;
      return '';
    }
    function resultName(r) {
      if (r.num) return r.num;
      return r.nn ? T('result.unnumbered_label', { kind: r.kind }) : r.kind;
    }
    function resultPos(ri) {
      var r = D.results[ri], f = fams[r.f], p = L.results[ri];
      return [f.x + p[0] * f.r, f.y + p[1] * f.r];
    }
    function leanPos(li) {
      var l = D.lean[li], f = fams[l.f], p = L.lean[li];
      return [f.x + p[0] * f.r, f.y + p[1] * f.r];
    }
    function objPos(o) {
      if (o.kind === 'r') return resultPos(o.i);
      if (o.kind === 'l') return leanPos(o.i);
      if (o.kind === 'f') return [fams[o.i].x, fams[o.i].y];
      if (o.kind === 'p') {
        var p = D.papers[o.i], f = fams[p.f], ring = L.papers[o.i];
        var a = ring[4] - ring[3] >= TAU - 1e-3 ? -Math.PI / 2 : (ring[3] + ring[4]) / 2;
        return [f.x + ring[2] * f.r * Math.cos(a), f.y + ring[2] * f.r * Math.sin(a)];
      }
      return [0, 0];
    }

    /* ---- The Loom: citations between families, bundled through discipline hubs */
    var fibres = [];        // { from, to, w, pts }
    var fibreCache = {};    // zoom bucket -> { rest: [Path2D], lit: {} }
    function buildFibres() {
      var wheel = L.wheel, rIn = wheel.rIn;
      var links = [];
      D.links.forEach(function (row) {
        if (row[2]) links.push({ from: row[0], to: row[1], w: row[2] });
        if (row[3]) links.push({ from: row[1], to: row[0], w: row[3] });
      });
      var routes = links.length ? Loom.bundle({
        cx: 0, cy: 0, R: rIn, at: fams.map(function (f) { return f.a; }), group: fams.map(function (f) { return f.d; }),
        hub: wheel.sectors.map(function (s) { return s[2]; }), links: links.map(function (l) { return [l.from, l.to]; }),
        rimR: rIn - 0.6, hubR: 0.8 * rIn, lanes: [0.36 * rIn, 0.66 * rIn], beta: 0.85, leave: 0.04 * rIn,
        fibrePitch: 0.5, localGain: 0.22, localDepth: [1.5, 0.2 * rIn], px: 0.6, shape: 'swoop'
      }) : [];
      fibres = links.map(function (l, k) { return { from: l.from, to: l.to, w: l.w, pts: routes[k].pts }; });
    }
    function fibreSet(k) {
      var bucket = Math.pow(2, Math.round(Math.log(k) / Math.LN2 * 4) / 4);
      var c = fibreCache[bucket];
      if (c) return c;
      var s = 1 / bucket;
      c = fibreCache[bucket] = { k: bucket, rest: [], lit: {} };
      fibres.forEach(function (f) {
        var g = Math.sqrt(f.w);
        var tp = Loom.taper({ start: 0.3 * s, body: (0.95 + 0.45 * g) * s, end: 0.7 * s * Math.max(1, g * 0.8), rise: 26 * s, fall: 20 * s, swell: 0.22 });
        c.rest.push(new Path2D(Loom.fibreStroke(f.pts, { width: tp, step: 2 * s, minPiece: 2 * s })));
      });
      return c;
    }
    function litFibre(c, k) {
      if (c.lit[k]) return c.lit[k];
      var s = 1 / c.k, f = fibres[k], g = Math.sqrt(f.w);
      var tp = Loom.taper({ start: 0.5 * s, body: (1.5 + 0.5 * g) * s, end: 1.1 * s * Math.max(1, g * 0.7), rise: 30 * s, fall: 22 * s, swell: 0.18 });
      return (c.lit[k] = new Path2D(Loom.fibreStroke(f.pts, { width: tp, step: 2 * s, minPiece: 2 * s })));
    }

    /* ---- Canvas size ---------------------------------------------------- */
    function chromeBoxes() {
      var out = [], sr = canvas.getBoundingClientRect();
      [toolsEl, helpEl].forEach(function (el) {
        if (!el || el.hidden || !el.offsetParent) return;
        var b = el.getBoundingClientRect();
        if (b.width && b.height) out.push({ x0: b.left - sr.left - 6, x1: b.right - sr.left + 6, y0: b.top - sr.top - 6, y1: b.bottom - sr.top + 6 });
      });
      return out;
    }
    var chrome = [];
    function resize() {
      var rect = canvas.getBoundingClientRect();
      var w = Math.max(1, Math.round(rect.width)), h = Math.max(1, Math.round(rect.height));
      var d = window.devicePixelRatio || 1;
      if (w === W && h === H && d === dpr) return false;
      var cx = W ? (W / 2 - view.tx) / view.k : 0, cy = H ? (H / 2 - view.ty) / view.k : 0;
      W = w; H = h; dpr = d;
      canvas.width = Math.round(w * d); canvas.height = Math.round(h * d);
      chrome = chromeBoxes();
      if (!D) return true;
      computeFit();
      if (viewFitted) setView(fitView());
      else { view.tx = W / 2 - cx * view.k; view.ty = H / 2 - cy * view.k; }
      return true;
    }

    /* ---- Discipline names round the wheel --------------------------------- */
    var DISC_FONT = '600 13.5px ' + SANS, DISC_COUNT_FONT = '400 12px ' + SANS, DISC_LEAD = 16;
    function discLabelText(di) {
      var d = D.disciplines[di];
      var lines = fitLines(d.name, DISC_FONT, 176, 1) || balancedLines(d.name, 2, DISC_FONT);
      var countLine = count('families', d.families.length);
      var w = Math.max(lines.width, textWidth(countLine, DISC_COUNT_FONT));
      return { lines: lines.lines, count: countLine, w: w, h: lines.lines.length * DISC_LEAD + 15 };
    }
    var discText = [], compactLabels = false;
    // Where the names stand for a view: each beside its sector, hugging the
    // wheel, set one above another on its side so none covers another.
    function placeDiscLabels(v, skip) {
      var sectors = L.wheel.sectors, cx = v.tx, cy = v.ty, k = v.k;
      var hull = L.wheel.rOut * k + 12;
      var sides = { '1': [], '-1': [] };
      sectors.forEach(function (s, di) {
        if (skip && skip(di)) return;
        var mid = s[2], ro = s[3] * k + 4;
        var ax = cx + ro * Math.cos(mid), ay = cy + ro * Math.sin(mid);
        var side = Math.cos(mid) >= 0 ? 1 : -1;
        var t = discText[di];
        if (!t) return;
        sides[side].push({ di: di, ax: ax, ay: ay, side: side, w: t.w, h: t.h, y: ay - t.h / 2, mid: mid });
      });
      var out = [];
      [1, -1].forEach(function (side) {
        var list = sides[side].sort(function (a, b) { return a.ay - b.ay; });
        // Down then up, so the stack keeps its order and stays near its anchors.
        for (var i = 1; i < list.length; i++) list[i].y = Math.max(list[i].y, list[i - 1].y + list[i - 1].h + 6);
        for (var j = list.length - 2; j >= 0; j--) list[j].y = Math.min(list[j].y, list[j + 1].y - list[j].h - 6);
        list.forEach(function (q) {
          var near = q.y > cy ? q.y : q.y + q.h < cy ? q.y + q.h : cy;
          var dy = Math.abs(near - cy);
          var reach = dy < hull ? Math.sqrt(hull * hull - dy * dy) : 0;
          var x = side > 0 ? Math.max(cx + reach + 8, q.ax + 10) : Math.min(cx - reach - 8, q.ax - 10);
          q.x0 = side > 0 ? x : x - q.w;
          q.x1 = q.x0 + q.w;
          q.y0 = q.y; q.y1 = q.y + q.h;
          out.push(q);
        });
      });
      return out;
    }
    function labelsInside(list, pad) {
      return list.every(function (q) {
        if (q.x0 < pad || q.x1 > W - pad || q.y0 < pad || q.y1 > H - pad) return false;
        return !chrome.some(function (c) { return boxesMeet(q, c, 0); });
      });
    }
    function computeFit() {
      discText = D.disciplines.map(function (d, di) { return discLabelText(di); });
      var rOut = L.wheel.rOut;
      var k0 = Math.min(W, H) / (2 * rOut) * 0.98, k = k0, fits = false;
      for (var it = 0; it < 60; it++) {
        var v = { k: k, tx: W / 2, ty: H / 2 };
        if (labelsInside(placeDiscLabels(v), 10)) { fits = true; break; }
        k *= 0.97;
      }
      // A canvas too narrow to set the names beside the wheel (a phone's Map
      // view) gives the wheel the room; the names stand in the list and on plates.
      compactLabels = !fits || k < k0 * 0.55;
      fitK = compactLabels ? k0 * 0.94 : k;
    }
    function fitView() { return { k: fitK, tx: W / 2, ty: H / 2 }; }
    function setView(v) { view.k = v.k; view.tx = v.tx; view.ty = v.ty; }

    /* ---- Camera (the Plectis universe's flight) ---------------------------- */
    function viewNow() { return { k: view.k, tx: view.tx, ty: view.ty, fitted: viewFitted }; }
    var RHO = 1.4;
    function flightPath(from, to, span) {
      var w0 = span / from.k, w1 = span / to.k;
      var dx = to.cx - from.cx, dy = to.cy - from.cy, d2 = dx * dx + dy * dy, u1 = Math.sqrt(d2);
      if (!(u1 > Math.min(w0, w1) * 0.9) || from.k <= fitK * 1.25 || to.k <= fitK * 1.25) return null;
      var rho2 = RHO * RHO, rho4 = rho2 * rho2;
      var b0 = (w1 * w1 - w0 * w0 + rho4 * d2) / (2 * w0 * rho2 * u1);
      var b1 = (w1 * w1 - w0 * w0 - rho4 * d2) / (2 * w1 * rho2 * u1);
      var r0 = Math.log(Math.sqrt(b0 * b0 + 1) - b0), r1 = Math.log(Math.sqrt(b1 * b1 + 1) - b1);
      var S = (r1 - r0) / RHO;
      if (!isFinite(S) || S <= 0) return null;
      var cosh = function (x) { return (Math.exp(x) + Math.exp(-x)) / 2; };
      var sinh = function (x) { return (Math.exp(x) - Math.exp(-x)) / 2; };
      var tanh = function (x) { var e2 = Math.exp(2 * x); return (e2 - 1) / (e2 + 1); };
      var c0 = cosh(r0);
      return {
        ms: S * 1000 * RHO / Math.SQRT2 * 0.62,
        at: function (t) {
          var s = t * S;
          var u = w0 / rho2 * (c0 * tanh(RHO * s + r0) - sinh(r0));
          var wide = w0 * c0 / cosh(RHO * s + r0);
          if (t >= 1) return [to.cx, to.cy, to.k];
          return [from.cx + u * dx / u1, from.cy + u * dy / u1, span / wide];
        }
      };
    }
    function cameraTo(target, fitted, delay) {
      if (cameraFrame) cancelAnimationFrame(cameraFrame);
      cameraFrame = 0;
      var finish = function () {
        cameraGoal = null; moving = false;
        setView(target);
        viewFitted = !!fitted;
        draw();
      };
      cameraGoal = finish;
      if (reduceMotion || !window.requestAnimationFrame || !W) { finish(); return; }
      var from = { k: view.k, cx: (W / 2 - view.tx) / view.k, cy: (H / 2 - view.ty) / view.k };
      var to = { k: target.k, cx: (W / 2 - target.tx) / target.k, cy: (H / 2 - target.ty) / target.k };
      var duration = Math.min(650, 300 + 120 * Math.abs(Math.log(to.k / from.k) / Math.LN2));
      var flight = flightPath(from, to, Math.max(W, H));
      if (flight) duration = Math.max(duration, Math.min(900, flight.ms));
      var start = null;
      viewFitted = false;
      moving = true;
      var step = function (now) {
        if (start === null) start = now + (delay || 0);
        var t = clamp((now - start) / duration, 0, 1), e = easeInOut(t), k, cx, cy;
        if (flight) { var at = flight.at(e); k = at[2]; cx = at[0]; cy = at[1]; }
        else {
          k = from.k * Math.pow(to.k / from.k, e);
          cx = from.cx + (to.cx - from.cx) * e; cy = from.cy + (to.cy - from.cy) * e;
        }
        view.k = k; view.tx = W / 2 - cx * k; view.ty = H / 2 - cy * k;
        paint();
        if (t < 1) cameraFrame = requestAnimationFrame(step);
        else { cameraFrame = 0; finish(); }
      };
      cameraFrame = requestAnimationFrame(step);
    }
    function sectorFrame(di) {
      var s = L.wheel.sectors[di], pts = [];
      var k = fitK * 2;
      for (var it = 0; it < 4; it++) {
        pts = [];
        var reach = s[3] + 190 / k;
        for (var a = s[0]; a <= s[1] + 1e-9; a += (s[1] - s[0]) / 12) {
          pts.push([L.wheel.rIn * 0.96 * Math.cos(a), L.wheel.rIn * 0.96 * Math.sin(a)]);
          pts.push([reach * Math.cos(a), reach * Math.sin(a)]);
        }
        var x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
        pts.forEach(function (p) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); });
        k = clamp(Math.min((W - 48) / (x1 - x0), (H - 48) / (y1 - y0)), fitK, fitK * 7);
      }
      return { k: k, tx: W / 2 - k * (x0 + x1) / 2, ty: H / 2 - k * (y0 + y1) / 2 };
    }
    function familyFrame(fi) {
      var f = fams[fi], hasF = (L.fibres[fi] || []).length > 0;
      var mx = hasF ? 205 : 70, my = hasF ? 46 : 40;
      var ext = hasF ? 1.3 : 1.08;
      var k = Math.min((W - 2 * mx) / (2 * ext * f.r), (H - 2 * my) / (2 * ext * f.r));
      k = clamp(k, fitK * 1.5, 600);
      return { k: k, tx: W / 2 - k * f.x, ty: H / 2 - k * f.y };
    }
    function frameFor(o) {
      if (!o) return fitView();
      if (o.kind === 'd') return sectorFrame(o.i);
      return familyFrame(famOf(o));
    }

    /* ---- Levels --------------------------------------------------------- */
    function openFamily() {
      var o = sel ? obj(sel) : null;
      return famOf(o);
    }
    function focusDisc() {
      var o = sel ? obj(sel) : null;
      return o && o.kind === 'd' ? o.i : -1;
    }
    function screenR(fi) { return fams[fi].r * view.k; }
    function dotRadius(sr) { return clamp(sr * 0.05, 0.9, 4.6); }

    /* ---- Painting -------------------------------------------------------- */
    function draw() {
      if (drawPending) return;
      drawPending = true;
      requestAnimationFrame(function () { drawPending = false; paint(); });
    }

    function famAlphas(openF, ctxA) {
      var out = new Array(fams.length), so = sel ? obj(sel) : null;
      var hk = hover ? obj(hover) : null;
      var focusF = openF >= 0 ? openF : (hk && hk.kind === 'f' ? hk.i : -1);
      var fd = focusDisc(), hd = hk && hk.kind === 'd' ? hk.i : -1;
      for (var i = 0; i < fams.length; i++) {
        var a = 1;
        var picked = so && so.kind === 'f' && so.i === focusF;
        if (focusF >= 0 && openF < 0) a = i === focusF ? 1 : fams[focusF].hop[i] ? 0.95 : picked ? 0.32 : 0.5;
        else if (fd >= 0) a = fams[i].d === fd ? 1 : 0.32;
        else if (hd >= 0) a = fams[i].d === hd ? 1 : 0.55;
        if (matchFam) a *= matchFam[i] ? 1 : 0.22;
        if (openF >= 0 && i !== openF) a *= ctxA;
        out[i] = a;
      }
      return out;
    }

    function paint() {
      if (!D || !W) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      hitTargets = [];
      var k = view.k, tx = view.tx, ty = view.ty;
      var openF = openFamily();
      var srOpen = openF >= 0 ? screenR(openF) : 0;
      // The rest of the release gives way as a family's own map fills the view.
      var ctxA = openF >= 0 ? 1 - smooth((srOpen - 80) / 110) : 1;
      var openA = openF >= 0 ? smooth((srOpen - 60) / 70) : 0;
      var alphas = famAlphas(openF, ctxA);
      var hk = hover ? obj(hover) : null, so = sel ? obj(sel) : null;

      // Sector slices: the focused discipline lies on one flat slice, edged with a hairline.
      var fd = focusDisc(), hd = hk && hk.kind === 'd' ? hk.i : (hk ? discOf(hk) : -1);
      if (ctxA > 0.02) {
        L.wheel.sectors.forEach(function (s, di) {
          var lit = di === fd || (di === hd && fd < 0 && openF < 0);
          if (!lit) return;
          ctx.save();
          ctx.globalAlpha = ctxA * (di === fd ? 1 : 0.7);
          ctx.beginPath();
          ctx.arc(tx, ty, (s[3] + 1.2) * k, s[0], s[1]);
          ctx.arc(tx, ty, L.wheel.rIn * 0.985 * k, s[1], s[0], true);
          ctx.closePath();
          ctx.fillStyle = palette.slice; ctx.fill();
          ctx.lineWidth = 0.8; ctx.strokeStyle = palette.structFaint; ctx.stroke();
          ctx.restore();
        });
        // A fine tick between sectors, at the inner rim.
        ctx.save();
        ctx.globalAlpha = ctxA;
        ctx.strokeStyle = palette.structFaint; ctx.lineWidth = 0.8;
        ctx.beginPath();
        L.wheel.sectors.forEach(function (s) {
          var a = s[0] - L.wheel.gap / 2, r0 = L.wheel.rIn * 0.97 * k, r1 = L.wheel.rIn * 0.97 * k - 7;
          ctx.moveTo(tx + r0 * Math.cos(a), ty + r0 * Math.sin(a));
          ctx.lineTo(tx + r1 * Math.cos(a), ty + r1 * Math.sin(a));
        });
        ctx.stroke();
        ctx.restore();
      }

      // The Loom.
      if (ctxA > 0.02 && fibres.length) paintFibres(alphas, openF, ctxA, hk);

      // Every family's own small map.
      var margin = 40;
      for (var fi = 0; fi < fams.length; fi++) {
        var a = alphas[fi];
        if (a < 0.01) continue;
        var f = fams[fi], sx = f.x * k + tx, sy = f.y * k + ty, sr = f.r * k;
        if (sx + sr * 1.4 < -margin || sx - sr * 1.4 > W + margin || sy + sr * 1.4 < -margin || sy - sr * 1.4 > H + margin) continue;
        paintFamily(fi, sx, sy, sr, a, fi === openF ? openA : 0);
      }

      // Words, then the lines that must go round them, then the plates.
      var plan = planLabels(openF, openA, ctxA, alphas);
      if (openF >= 0 && openA > 0.01) paintOpenLines(openF, openA, plan);
      paintLabels(plan);
      paintPlates(plan);
      lastPlan = plan;
      if (window.__universeDebug) window.__universeDebug.plan = plan;
    }

    function paintFibres(alphas, openF, ctxA, hk) {
      var c = fibreSet(view.k);
      var k = view.k;
      var focusF = openF >= 0 ? openF : (hk && hk.kind === 'f' ? hk.i : (sel && obj(sel) && obj(sel).kind === 'f' ? obj(sel).i : -1));
      var fd = focusDisc();
      ctx.save();
      ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * view.tx, dpr * view.ty);
      var lit = [];
      fibres.forEach(function (f, i) {
        var mine = focusF >= 0 && (f.from === focusF || f.to === focusF);
        if (mine) { lit.push(i); return; }
        var a = 0.85;
        if (focusF >= 0) a = 0.18;
        else if (fd >= 0) a = fams[f.from].d === fd || fams[f.to].d === fd ? 0.9 : 0.22;
        if (matchFam) a *= matchFam[f.from] || matchFam[f.to] ? 1 : 0.3;
        ctx.globalAlpha = a * ctxA;
        ctx.fillStyle = palette.fibre;
        ctx.fill(c.rest[i]);
      });
      lit.forEach(function (i) {
        var f = fibres[i];
        ctx.globalAlpha = ctxA;
        ctx.fillStyle = f.from === focusF ? palette.cites : palette.cited;
        ctx.fill(litFibre(c, i));
      });
      ctx.restore();
      // A lit fibre runs on from the rim to its family's map.
      if (focusF >= 0 && lit.length) {
        ctx.save();
        ctx.lineWidth = 1;
        ctx.globalAlpha = ctxA * 0.8;
        lit.forEach(function (i) {
          var f = fibres[i];
          [[f.from, palette.cites, f.from === focusF], [f.to, palette.cited, f.to === focusF]].forEach(function (end) {
            var fm = fams[end[0]], rr = Math.hypot(fm.x, fm.y) - fm.r;
            var r0 = (L.wheel.rIn - 0.6) * k;
            if (rr * k - r0 < 2) return;
            ctx.strokeStyle = f.from === focusF ? palette.cites : palette.cited;
            ctx.beginPath();
            ctx.moveTo(view.tx + r0 * Math.cos(fm.a), view.ty + r0 * Math.sin(fm.a));
            ctx.lineTo(view.tx + rr * k * Math.cos(fm.a), view.ty + rr * k * Math.sin(fm.a));
            ctx.stroke();
          });
        });
        ctx.restore();
      }
    }

    function diamond(x, y, s) {
      ctx.moveTo(x, y - s); ctx.lineTo(x + s, y); ctx.lineTo(x, y + s); ctx.lineTo(x - s, y); ctx.closePath();
    }

    function paintFamily(fi, sx, sy, sr, a, open) {
      var f = fams[fi], fd = f.data, k = view.k;
      var dr = dotRadius(sr) * (1 + 0.35 * open);
      var hk = hover ? obj(hover) : null, so = sel ? obj(sel) : null;
      var isHot = (hk && famOf(hk) === fi && hk.kind === 'f') || (so && so.kind === 'f' && so.i === fi);
      ctx.save();
      ctx.globalAlpha = a;
      // The family's ground: a faint disc, so a small map reads as one thing.
      ctx.beginPath();
      ctx.arc(sx, sy, sr, 0, TAU);
      ctx.fillStyle = palette.cloud;
      ctx.fill();
      if (isHot && open < 0.5) { ctx.lineWidth = 1.2; ctx.strokeStyle = palette.focus; ctx.stroke(); }
      // Outside checks on the family: HOL Light (a brick ring), finite parts (a dotted one).
      if (fd.hol) {
        ctx.beginPath(); ctx.arc(sx, sy, sr + Math.max(1.5, sr * 0.05), 0, TAU);
        ctx.lineWidth = clamp(sr * 0.022, 0.9, 1.6); ctx.strokeStyle = palette.brick; ctx.stroke();
      }
      if (fd.fin) {
        ctx.beginPath(); ctx.arc(sx, sy, sr + Math.max(3.2, sr * 0.11), 0, TAU);
        ctx.lineWidth = clamp(sr * 0.022, 0.9, 1.6); ctx.setLineDash([0.1, Math.max(2.6, sr * 0.045)]);
        ctx.lineCap = 'round'; ctx.strokeStyle = palette.brick; ctx.stroke(); ctx.setLineDash([]); ctx.lineCap = 'butt';
      }
      // Paper rings and arcs.
      var ringA = smooth((sr - 5) / 12);
      if (ringA > 0) {
        ctx.globalAlpha = a * ringA;
        ctx.lineWidth = sr > 60 ? 1.1 : 0.8;
        fd.papers.forEach(function (pi) {
          var g = L.papers[pi];
          var hot = (hk && hk.kind === 'p' && hk.i === pi) || (so && so.kind === 'p' && so.i === pi);
          ctx.strokeStyle = hot ? palette.ink : palette.struct;
          ctx.lineWidth = hot ? 2 : (sr > 60 ? 1.1 : 0.8);
          ctx.beginPath();
          ctx.arc(sx + g[0] * sr, sy + g[1] * sr, g[2] * sr, g[3], g[4]);
          ctx.stroke();
        });
        // The Lean statements' ring.
        if (L.leanR[fi] && sr > 22) {
          ctx.globalAlpha = a * smooth((sr - 22) / 30) * 0.9;
          ctx.setLineDash([1.5, 3.5]);
          ctx.lineWidth = 0.8; ctx.strokeStyle = palette.struct;
          ctx.beginPath(); ctx.arc(sx, sy, L.leanR[fi] * sr, 0, TAU); ctx.stroke();
          ctx.setLineDash([]);
        }
      }
      ctx.globalAlpha = a;
      // Threads at rest, before the marks, only once the map is open (see paintOpenLines).
      // Headline results: a disc when paired with a Lean statement, a ring when not.
      var dim = function (key) { return matches && !matches[key] ? 0.28 : 1; };
      fd.papers.forEach(function (pi) {
        D.papers[pi].results.forEach(function (ri) {
          var p = L.results[ri], x = sx + p[0] * sr, y = sy + p[1] * sr, r = D.results[ri];
          ctx.globalAlpha = a * dim(r.id);
          ctx.beginPath();
          ctx.arc(x, y, dr, 0, TAU);
          if (r.lean.length) { ctx.fillStyle = palette.paired; ctx.fill(); }
          else { ctx.fillStyle = palette.ground; ctx.fill(); ctx.lineWidth = Math.max(0.8, dr * 0.42); ctx.strokeStyle = palette.struct; ctx.stroke(); }
        });
      });
      // Lean statements: diamonds filled by how many outside groups accepted their re-run.
      fd.lean.forEach(function (li) {
        var p = L.lean[li], x = sx + p[0] * sr, y = sy + p[1] * sr, l = D.lean[li], n = l.acc.length;
        var s = dr * 1.32;
        ctx.globalAlpha = a * dim(l.id);
        ctx.beginPath(); diamond(x, y, s);
        ctx.fillStyle = n ? palette.lean[n] : palette.ground; ctx.fill();
        ctx.lineWidth = Math.max(0.8, s * 0.28); ctx.strokeStyle = palette.steel; ctx.stroke();
        if (l.holes && s > 2.2) {
          ctx.beginPath(); ctx.arc(x, y, s * 0.34, 0, TAU); ctx.fillStyle = palette.ground; ctx.fill();
        }
      });
      ctx.restore();
    }

    /* ---- Labels: placed in priority order, none covering another or a mark */
    var PLATE_FONT = '500 13.5px ' + SERIF, PLATE_SUB = '400 12px ' + SANS, PLATE_LEAD = 17;
    var NAME_FONT = '400 12.5px ' + SERIF, NAME_LEAD = 15;
    var END_FONT = '400 12.5px ' + SERIF, PAPER_FONT = '400 13px ' + SERIF, LEAN_FONT = '400 11.5px ' + MONO;
    var NUM_FONT = '400 11px ' + SANS, CAP_FONT = 'italic 400 11.5px ' + SANS;

    function planLabels(openF, openA, ctxA, alphas) {
      var plan = { disc: [], names: [], open: [], plates: [], marks: [], lines: [], leaders: [], boxes: [] };
      var taken = [];
      var free = function (b) {
        if (b.x0 < 4 || b.x1 > W - 4 || b.y0 < 4 || b.y1 > H - 4) return false;
        for (var i = 0; i < chrome.length; i++) if (boxesMeet(b, chrome[i], 0)) return false;
        for (var j = 0; j < taken.length; j++) if (boxesMeet(b, taken[j], 1)) return false;
        return true;
      };
      var k = view.k;
      // Marks the words must keep off: the open family's dots, diamonds and rings.
      var marks = [];
      if (openF >= 0 && openA > 0.01) marks = openMarks(openF);
      plan.marks = marks;
      // Plates first: the hovered and the selected object, so the names give way.
      var hk = hover ? obj(hover) : null, so = sel ? obj(sel) : null;
      var plateFor = [];
      if (so && (so.kind === 'r' || so.kind === 'l' || so.kind === 'p' || (so.kind === 'f' && openA < 0.5))) plateFor.push(so);
      if (hk && (!so || hk.key !== so.key) && (hk.kind !== 'd' || compactLabels)) plateFor.push(hk);
      // The discipline names' places are known before they are set; a plate keeps off them where it can.
      var discKeep = ctxA > 0.3 && !(compactLabels && view.k < fitK * 1.6) ?
        placeDiscLabels(view, function (di) { return di === focusDisc(); }).map(function (q) { return { x0: q.x0, x1: q.x1, y0: q.y0, y1: q.y1 }; }) : [];
      plateFor.forEach(function (o) {
        var p = namePlate(o, marks.concat(taken, discKeep, discKeep));
        if (p) { plan.plates.push(p); taken.push({ x0: p.box.x0, x1: p.box.x1, y0: p.box.y0, y1: p.box.y1, plate: true }); }
      });
      // The discipline names while the wheel is in view; in a discipline, its
      // families' names come first and the other disciplines' names take what room is left.
      if (ctxA > 0.3 && !(compactLabels && view.k < fitK * 1.6)) {
        var fd = focusDisc();
        var wantNames = fd >= 0 || k >= fitK * 1.9;
        if (wantNames && fd >= 0) placeNames(plan, taken, fd, alphas, ctxA);
        var list = placeDiscLabels(view, function (di) { return di === fd; });
        list.forEach(function (q) {
          var t = discText[q.di];
          var b = { x0: q.x0, x1: q.x1, y0: q.y0, y1: q.y1 };
          if (!free(b)) return;
          var lead = discLeader(q), dots = [];
          if (lead) {
            for (var s2 = 1; s2 < lead.length; s2++) {
              var p0 = lead[s2 - 1], p1 = lead[s2], n2 = Math.max(1, Math.ceil(Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 6));
              for (var u2 = 0; u2 <= n2; u2++) {
                var lx2 = p0[0] + (p1[0] - p0[0]) * u2 / n2, ly2 = p0[1] + (p1[1] - p0[1]) * u2 / n2;
                dots.push({ x0: lx2 - 2, x1: lx2 + 2, y0: ly2 - 2, y1: ly2 + 2, leader: true });
              }
            }
            // A leader may not cross a word already standing.
            for (var d2 = 0; d2 < dots.length; d2++) for (var j2 = 0; j2 < taken.length; j2++) if (!taken[j2].leader && boxesMeet(dots[d2], taken[j2], 0)) return;
            plan.leaders.push({ ink: 'leader', pts: lead });
          }
          taken.push(b);
          dots.forEach(function (d3) { taken.push(d3); });
          plan.disc.push({ di: q.di, x: q.x0, y: q.y0, side: q.side, t: t, ax: q.ax, ay: q.ay, box: b, alpha: ctxA,
                           hot: (hk && hk.kind === 'd' && hk.i === q.di) || discOf(hk) === q.di });
          hitTargets.push({ box: b, key: D.disciplines[q.di].id });
        });
        if (wantNames && fd < 0) placeNames(plan, taken, fd, alphas, ctxA);
      }
      if (openF >= 0 && openA > 0.01) placeOpen(plan, openF, openA, taken, marks, free);
      plan.boxes = taken;
      return plan;
    }

    function rayRoom(cx, cy, a, r0) {
      // How far a ray from the wheel's centre runs past r0 before it leaves the canvas.
      var dx = Math.cos(a), dy = Math.sin(a), best = Infinity;
      if (dx > 1e-6) best = Math.min(best, (W - 8 - cx) / dx);
      if (dx < -1e-6) best = Math.min(best, (8 - cx) / dx);
      if (dy > 1e-6) best = Math.min(best, (H - 8 - cy) / dy);
      if (dy < -1e-6) best = Math.min(best, (8 - cy) / dy);
      return best - r0;
    }
    /* Family names, set along their radius outside the band as the system map
       names a family's components. Close to the band each name keeps its
       family's angle; where names crowd, they fan out along the rim in the
       families' order (clusters of names centred on their families, the way
       pie labels are spread), each tied to its place by a fine polar leader. */
    function placeNames(plan, taken, fd, alphas, ctxA) {
      var k = view.k, cx = view.tx, cy = view.ty;
      // The small maps on the canvas are marks a name keeps off.
      var discs = [];
      fams.forEach(function (f, fi) {
        if (alphas[fi] < 0.02) return;
        var x = f.x * k + cx, y = f.y * k + cy, r = f.r * k + 4;
        if (x + r < 0 || x - r > W || y + r < 0 || y - r > H) return;
        discs.push([x, y, r]);
      });
      var onDisc = function (q) {
        var qx = (q.x0 + q.x1) / 2, qy = (q.y0 + q.y1) / 2, h = (q.x1 - q.x0) / 2;
        for (var i = 0; i < discs.length; i++) {
          var d = discs[i], dx = qx - d[0], dy = qy - d[1], rr = d[2] + h * 0.8;
          if (dx * dx + dy * dy < rr * rr) return true;
        }
        return false;
      };
      L.wheel.sectors.forEach(function (s, di) {
        if (fd >= 0 && di !== fd) return;
        var rEdge = s[3] * k + 4, r0 = rEdge + 30;
        var mid = s[2], mx = cx + rEdge * Math.cos(mid), my = cy + rEdge * Math.sin(mid);
        if (fd < 0 && (mx < -200 || mx > W + 200 || my < -200 || my > H + 200)) return;
        var items = [];
        D.disciplines[di].families.forEach(function (fi) {
          if (alphas[fi] < 0.3) return;
          var f = fams[fi];
          var room = Math.min(330, rayRoom(cx, cy, f.a, r0));
          var t = room >= 60 ? fitLines(D.families[fi].title, NAME_FONT, Math.max(60, room), 2) : null;
          if (!t) t = fitLines(D.families[fi].title, NAME_FONT, 330, 2);
          if (!t) return;
          items.push({ fi: fi, a: f.a, t: t, need: (t.lines.length * NAME_LEAD + 3) / r0 });
        });
        items.sort(function (p, q) { return p.a - q.a; });
        // Spread: merge crowding neighbours into clusters, each centred on its members.
        var clusters = items.map(function (it) { return { items: [it], size: it.need }; });
        var place = function (c) {
          var off = 0, sum = 0;
          c.items.forEach(function (it) { sum += it.a - (off + it.need / 2); off += it.need; });
          c.lo = sum / c.items.length;
        };
        clusters.forEach(place);
        for (var guard = 0; guard < 400; guard++) {
          var merged = false;
          for (var c = 1; c < clusters.length; c++) {
            var A = clusters[c - 1], B = clusters[c];
            if (A.lo + A.size > B.lo) {
              var C = { items: A.items.concat(B.items), size: A.size + B.size };
              place(C);
              clusters.splice(c - 1, 2, C);
              merged = true;
              break;
            }
          }
          if (!merged) break;
        }
        clusters.forEach(function (c) {
          var off = 0;
          c.items.forEach(function (it) {
            var b = c.lo + off + it.need / 2;
            off += it.need;
            var right = Math.cos(b) >= 0;
            var room = rayRoom(cx, cy, b, r0);
            if (it.t.width > room) return;
            var half = (it.t.lines.length * NAME_LEAD) / 2 + 1;
            var samples = [];
            for (var along = 0; along <= it.t.width + 0.1; along += 8) {
              var sx = cx + (r0 + along) * Math.cos(b), sy = cy + (r0 + along) * Math.sin(b);
              samples.push({ x0: sx - half, x1: sx + half, y0: sy - half, y1: sy + half });
            }
            // A name stands whole on the canvas, clear of every other word.
            for (var i = 0; i < samples.length; i++) {
              var q = samples[i], qx = (q.x0 + q.x1) / 2, qy = (q.y0 + q.y1) / 2;
              if (qx < 6 || qx > W - 6 || qy < 6 || qy > H - 6) return;
              if (onDisc(q)) return;
              for (var j = 0; j < chrome.length; j++) if (boxesMeet(q, chrome[j], 0)) return;
              for (var j2 = 0; j2 < taken.length; j2++) if (boxesMeet(q, taken[j2], 1)) return;
            }
            var lead = null;
            if (Math.abs(Loom.turn(it.a, b)) * r0 > 2) {
              var a1 = it.a + Loom.turn(it.a, b);
              lead = Loom.polarXY(cx, cy, Loom.polarBezier([it.a, rEdge], [it.a, rEdge + 13], [a1, r0 - 15], [a1, r0 - 4], 3));
            } else {
              lead = [[cx + rEdge * Math.cos(it.a), cy + rEdge * Math.sin(it.a)], [cx + (r0 - 4) * Math.cos(it.a), cy + (r0 - 4) * Math.sin(it.a)]];
            }
            samples.forEach(function (q2) { taken.push(q2); });
            plan.leaders.push({ ink: 'name', fi: it.fi, pts: lead });
            plan.names.push({ fi: it.fi, a: b, r0: r0, ox: cx + r0 * Math.cos(b), oy: cy + r0 * Math.sin(b), t: it.t, alpha: alphas[it.fi] * ctxA, samples: samples, lead: lead });
            samples.forEach(function (q3) { hitTargets.push({ box: q3, key: D.families[it.fi].id }); });
          });
        });
      });
    }

    // The open family's marks, in screen space.
    function openMarks(fi) {
      var f = fams[fi], k = view.k, sx = f.x * k + view.tx, sy = f.y * k + view.ty, sr = f.r * k;
      var dr = dotRadius(sr) * 1.35 + 3, out = [];
      f.data.papers.forEach(function (pi) {
        D.papers[pi].results.forEach(function (ri) {
          var p = L.results[ri], x = sx + p[0] * sr, y = sy + p[1] * sr;
          out.push({ x0: x - dr, x1: x + dr, y0: y - dr, y1: y + dr, key: D.results[ri].id });
        });
        var g = L.papers[pi], rr = g[2] * sr, span = g[4] - g[3], n = Math.max(6, Math.ceil(span * rr / 9));
        for (var j = 0; j <= n; j++) {
          var a = g[3] + span * j / n, x2 = sx + g[0] * sr + rr * Math.cos(a), y2 = sy + g[1] * sr + rr * Math.sin(a);
          out.push({ x0: x2 - 3, x1: x2 + 3, y0: y2 - 3, y1: y2 + 3, ring: pi });
        }
      });
      f.data.lean.forEach(function (li) {
        var p = L.lean[li], x = sx + p[0] * sr, y = sy + p[1] * sr, s = dr * 1.2;
        out.push({ x0: x - s, x1: x + s, y0: y - s, y1: y + s, key: D.lean[li].id });
      });
      // The outside checks' rings round the family are lines the words keep off too.
      [f.data.hol ? sr + Math.max(1.5, sr * 0.05) : 0, f.data.fin ? sr + Math.max(3.2, sr * 0.11) : 0].forEach(function (er) {
        if (!er) return;
        var me = Math.ceil(TAU * er / 9);
        for (var e2 = 0; e2 < me; e2++) {
          var ae = TAU * e2 / me, xe = sx + er * Math.cos(ae), ye = sy + er * Math.sin(ae);
          out.push({ x0: xe - 3, x1: xe + 3, y0: ye - 3, y1: ye + 3, ring: -2 });
        }
      });
      if (L.leanR[fi]) {
        var rl = L.leanR[fi] * sr, m = Math.ceil(TAU * rl / 10);
        for (var q = 0; q < m; q++) {
          var a2 = TAU * q / m, x3 = sx + rl * Math.cos(a2), y3 = sy + rl * Math.sin(a2);
          out.push({ x0: x3 - 2.5, x1: x3 + 2.5, y0: y3 - 2.5, y1: y3 + 2.5, ring: -1 });
        }
      }
      return out;
    }

    function textBlock(lines, font, lead) {
      var w = 0;
      lines.forEach(function (l) { w = Math.max(w, textWidth(l, font)); });
      return { w: w, h: lines.length * lead };
    }

    function placeOpen(plan, fi, openA, taken, marks, free) {
      var f = fams[fi], k = view.k, sx = f.x * k + view.tx, sy = f.y * k + view.ty, sr = f.r * k;
      var clear = function (b) {
        if (!free(b)) return false;
        for (var i = 0; i < marks.length; i++) if (boxesMeet(b, marks[i], 0)) return false;
        return true;
      };
      var take = function (b) { taken.push(b); };
      var ENDR = 1.24;
      // Fibre ends: the other family's name, whole, beyond the end of its fibre.
      (L.fibres[fi] || []).forEach(function (fb, j) {
        var a = fb[0], g = fb[1], ex = sx + ENDR * sr * Math.cos(a), ey = sy + ENDR * sr * Math.sin(a);
        var right = Math.cos(a) >= 0;
        var item = { kind: 'end', g: g, a: a, ex: ex, ey: ey, way: fb[2], papers: fb[3], alpha: openA };
        var choices = [];
        var title = D.families[g].title;
        [190, 240].forEach(function (mw) { var t = fitLines(title, END_FONT, mw, 3); if (t) choices.push(t); });
        choices.push({ lines: [T('plate.family_short', { num: D.families[g].num })], width: textWidth(T('plate.family_short', { num: D.families[g].num }), END_FONT) });
        for (var c = 0; c < choices.length; c++) {
          var t = choices[c], bh = t.lines.length * NAME_LEAD;
          var offs = [0, -0.5, 0.5, -1, 1];
          for (var o = 0; o < offs.length; o++) {
            var gx = ex + (right ? 9 : -9), gy = ey + offs[o] * bh * 0.7 - bh / 2 + (Math.sin(a) * bh * 0.35);
            var b = { x0: right ? gx : gx - t.width, x1: right ? gx + t.width : gx, y0: gy, y1: gy + bh };
            if (clear(b)) {
              take(b);
              item.t = t; item.box = b; item.right = right;
              plan.open.push(item);
              hitTargets.push({ box: b, key: D.families[g].id, follow: true });
              return;
            }
          }
        }
        item.t = null;
        plan.open.push(item);
      });
      // The lead paper's title inside its ring, where it stands whole.
      f.data.papers.forEach(function (pi, n) {
        var g = L.papers[pi], whole = g[4] - g[3] >= TAU - 1e-3;
        var title = D.papers[pi].title;
        if (whole) {
          var inner = g[2] * sr * 2 * 0.74;
          var t = fitLines(title, PAPER_FONT, inner, 4);
          if (t && t.lines.length * 16 < g[2] * sr * 1.3) {
            var bh = t.lines.length * 16, b = { x0: sx - t.width / 2, x1: sx + t.width / 2, y0: sy - bh / 2, y1: sy + bh / 2 };
            if (clear(b)) { take(b); plan.open.push({ kind: 'paper', pi: pi, t: t, box: b, center: true, alpha: openA }); hitTargets.push({ box: b, key: D.papers[pi].id }); return; }
          }
          if (n === 0 && f.data.papers.length > 1) {
            var tag = T('family.lead');
            var tw = textWidth(tag, CAP_FONT), b2 = { x0: sx - tw / 2, x1: sx + tw / 2, y0: sy - 7, y1: sy + 7 };
            if (g[2] * sr * 1.6 > tw && clear(b2)) { take(b2); plan.open.push({ kind: 'cap', text: tag, box: b2, alpha: openA }); }
          }
          return;
        }
        // An arc's title just inside its arc, or beside it.
        var mid = (g[3] + g[4]) / 2, rr = g[2] * sr;
        var t2 = fitLines(title, PAPER_FONT, Math.min(220, Math.max(120, (g[4] - g[3]) * rr)), 3);
        if (!t2) return;
        var bh2 = t2.lines.length * 16;
        [1].some(function (side) {
          var rad = rr + side * (14 + bh2 * 0.6 + Math.abs(Math.cos(mid)) * t2.width * 0.5);
          var cxp = sx + rad * Math.cos(mid), cyp = sy + rad * Math.sin(mid);
          var b3 = { x0: cxp - t2.width / 2, x1: cxp + t2.width / 2, y0: cyp - bh2 / 2, y1: cyp + bh2 / 2 };
          if (Math.hypot(cxp - sx, cyp - sy) + Math.max(t2.width, bh2) / 2 > ENDR * sr - 6 && side > 0) return false;
          if (!clear(b3)) return false;
          take(b3);
          plan.open.push({ kind: 'paper', pi: pi, t: t2, box: b3, alpha: openA });
          hitTargets.push({ box: b3, key: D.papers[pi].id });
          return true;
        });
      });
      // Lean statements by name, beside their diamonds.
      f.data.lean.forEach(function (li) {
        var p = L.lean[li], x = sx + p[0] * sr, y = sy + p[1] * sr, a = Math.atan2(p[1], p[0]);
        var name = D.lean[li].name, w = textWidth(name, LEAN_FONT);
        var right = Math.cos(a) >= 0, d = dotRadius(sr) * 1.8 + 6;
        var spots = [[right ? x + d : x - d - w, y - 7], [right ? x + d : x - d - w, y - 7 + (Math.sin(a) >= 0 ? 12 : -12)],
                     [x - w / 2, Math.sin(a) >= 0 ? y + d : y - d - 14], [right ? x - d - w : x + d, y - 7],
                     [x - w / 2, Math.sin(a) >= 0 ? y - d - 14 : y + d]];
        for (var s = 0; s < spots.length; s++) {
          var b = { x0: spots[s][0], x1: spots[s][0] + w, y0: spots[s][1], y1: spots[s][1] + 14 };
          if (clear(b)) { take(b); plan.open.push({ kind: 'lean', li: li, text: name, box: b, alpha: openA }); hitTargets.push({ box: b, key: D.lean[li].id }); return; }
        }
      });
      // Each result's number in its paper, beside its dot.
      f.data.papers.forEach(function (pi) {
        D.papers[pi].results.forEach(function (ri) {
          var r = D.results[ri];
          if (!r.num) return;
          var m = /(\d[\w.]*)$/.exec(r.num), text = m ? m[1] : null;
          if (!text) return;
          var p = L.results[ri], x = sx + p[0] * sr, y = sy + p[1] * sr, g = L.papers[pi];
          var ox = x - (sx + g[0] * sr), oy = y - (sy + g[1] * sr), len = Math.hypot(ox, oy) || 1;
          var w = textWidth(text, NUM_FONT), d = dotRadius(sr) * 1.35 + 5;
          var tries = [[ox / len, oy / len], [-ox / len, -oy / len]];
          for (var q = 0; q < tries.length; q++) {
            var cxp = x + tries[q][0] * (d + w / 2), cyp = y + tries[q][1] * (d + 6);
            var b = { x0: cxp - w / 2, x1: cxp + w / 2, y0: cyp - 6.5, y1: cyp + 6.5 };
            if (clear(b)) { take(b); plan.open.push({ kind: 'num', ri: ri, text: text, box: b, alpha: openA }); return; }
          }
        });
      });
      // The Lean ring's caption.
      if (L.leanR[fi]) {
        var cap = T('plate.lean_ring'), cw = textWidth(cap, CAP_FONT), rl = L.leanR[fi] * sr;
        [Math.PI / 2, -Math.PI / 2].some(function (a) {
          var cyp = sy + (rl + 10) * Math.sin(a), b = { x0: sx - cw / 2, x1: sx + cw / 2, y0: cyp - 7, y1: cyp + 7 };
          if (!clear(b)) return false;
          take(b); plan.open.push({ kind: 'cap', text: cap, box: b, alpha: openA });
          return true;
        });
      }
    }

    /* ---- Name plates (the Plectis universe's namePlate, least covered of six spots) */
    function plateLines(o) {
      var name = nameOf(o), sub = '';
      if (o.kind === 'r') sub = D.papers[D.results[o.i].p].title;
      else if (o.kind === 'l') sub = D.lean[o.i].label !== D.lean[o.i].name ? D.lean[o.i].label : '';
      else if (o.kind === 'f') sub = T('family.plate', { num: D.families[o.i].num, discipline: D.disciplines[fams[o.i].d].name });
      else if (o.kind === 'p') sub = T('family.short', { num: D.families[D.papers[o.i].f].num });
      else if (o.kind === 'd') sub = count('families', D.disciplines[o.i].families.length);
      var maxW = Math.min(340, W - 40);
      var main = fitLines(name, PLATE_FONT, Math.min(300, maxW), 3) || fitLines(name, PLATE_FONT, maxW, 6) || balancedLines(name, 8, PLATE_FONT);
      var subT = sub ? (fitLines(sub, PLATE_SUB, Math.max(main.width, 220), 3) || balancedLines(sub, 5, PLATE_SUB)) : null;
      return { main: main, sub: subT };
    }
    function markOf(o) {
      var k = view.k, p, r;
      if (o.kind === 'd') {
        var sct = L.wheel.sectors[o.i], rr = sct[3] * k;
        return { x: view.tx + rr * Math.cos(sct[2]), y: view.ty + rr * Math.sin(sct[2]), r: 4 };
      }
      if (o.kind === 'f') { var f = fams[o.i]; return { x: f.x * k + view.tx, y: f.y * k + view.ty, r: f.r * k + 2 }; }
      p = objPos(o);
      var sr = screenR(famOf(o));
      r = o.kind === 'p' ? 4 : dotRadius(sr) * 1.5 + 2;
      return { x: p[0] * k + view.tx, y: p[1] * k + view.ty, r: r };
    }
    function namePlate(o, keepOut) {
      var m = markOf(o);
      if (m.x < -20 || m.x > W + 20 || m.y < -20 || m.y > H + 20) return null;
      var t = plateLines(o);
      var pad = 7, w = Math.max(t.main.width, t.sub ? t.sub.width : 0) + pad * 2;
      var h = t.main.lines.length * PLATE_LEAD + (t.sub ? t.sub.lines.length * 15 + 3 : 0) + pad * 2 - 2;
      var gap = m.r + 10;
      var spots = [[m.x + gap, m.y - h - 4], [m.x + gap, m.y + 4], [m.x - gap - w, m.y - h - 4], [m.x - gap - w, m.y + 4],
                   [m.x - w / 2, m.y - gap - h], [m.x - w / 2, m.y + gap]];
      var best = null, bestScore = Infinity;
      spots.forEach(function (s, i) {
        var x0 = clamp(s[0], 6, W - w - 6), y0 = clamp(s[1], 6, H - h - 6);
        var b = { x0: x0, x1: x0 + w, y0: y0, y1: y0 + h };
        var score = i * 4;
        keepOut.forEach(function (q) { score += overlap(b, q) * (q.ring !== undefined ? 0.6 : 1.5); });
        chrome.forEach(function (q) { score += overlap(b, q) * 4; });
        // Never over the mark itself.
        if (m.x + m.r > b.x0 && m.x - m.r < b.x1 && m.y + m.r > b.y0 && m.y - m.r < b.y1) score += 5000;
        if (score < bestScore) { bestScore = score; best = b; }
      });
      if (!best) return null;
      // The leader: from the mark's edge to the plate's nearest edge.
      var px = clamp(m.x, best.x0, best.x1), py = clamp(m.y, best.y0, best.y1);
      var dx = px - m.x, dy = py - m.y, len = Math.hypot(dx, dy) || 1;
      var leader = len > m.r + 3 ? [m.x + dx / len * (m.r + 1), m.y + dy / len * (m.r + 1), px, py] : null;
      return { key: o.key, box: best, t: t, pad: pad, leader: leader };
    }

    /* ---- The open family's lines: threads to Lean, fibres to other families */
    var routeCache = { key: '', routes: null };
    function paintOpenLines(fi, openA, plan) {
      var f = fams[fi], k = view.k, sx = f.x * k + view.tx, sy = f.y * k + view.ty, sr = f.r * k;
      var words = plan.boxes.filter(function (b) { return !b.ring && !b.plate; });
      // The routes depend on where the words stand relative to the family, so a
      // pan reuses them, moved; a zoom or a change of words finds them again.
      var sig = [fi, k.toFixed(4), words.length].concat(words.map(function (b) { return (b.x0 - sx).toFixed(1) + ',' + (b.y0 - sy).toFixed(1); })).join('|');
      var routes;
      if (routeCache.key === sig) {
        routes = routeCache.routes.map(function (r) {
          return { ink: r.ink, dash: r.dash, w: r.w, end: r.end, pair: r.pair, pts: r.rel.map(function (p) { return [p[0] + sx, p[1] + sy]; }) };
        });
      } else {
        routes = [];
        var obstacles = words.map(function (b) { return { x0: b.x0 - 4, x1: b.x1 + 4, y0: b.y0 - 4, y1: b.y1 + 4 }; });
        // Threads: each paired result to its Lean statement (chosen automatically, so dashed).
        f.data.lean.forEach(function (li) {
          var lp = L.lean[li], B = [sx + lp[0] * sr, sy + lp[1] * sr];
          D.lean[li].results.forEach(function (ri) {
            var rp = L.results[ri], A = [sx + rp[0] * sr, sy + rp[1] * sr];
            var obs = obstacles.filter(function (o) { return !insideBox(A, o) && !insideBox(B, o); });
            var way = shortestWay(A, B, obs) || [A, B];
            routes.push({ ink: 'steel', dash: true, w: 1.1, pair: [D.results[ri].id, D.lean[li].id], pts: trimEnds(way, dotRadius(sr) * 1.4 + 2, dotRadius(sr) * 1.7 + 2) });
          });
        });
        // Fibres: from each citing or cited paper to the end that names the other family.
        (L.fibres[fi] || []).forEach(function (fb) {
          var a = fb[0], E = [sx + 1.24 * sr * Math.cos(a), sy + 1.24 * sr * Math.sin(a)];
          var ends = plan.open.filter(function (it) { return it.kind === 'end' && it.g === fb[1] && it.box; }).map(function (it) { return it.box; });
          fb[3].forEach(function (pIdx) {
            var pi = f.data.papers[pIdx], g = L.papers[pi], whole = g[4] - g[3] >= TAU - 1e-3;
            var at = whole ? a : clampAngle(a, g[3], g[4]);
            var Sx = sx + g[0] * sr + g[2] * sr * Math.cos(at), Sy = sy + g[1] * sr + g[2] * sr * Math.sin(at);
            var r0 = Math.hypot(Sx - sx, Sy - sy), a0 = Math.atan2(Sy - sy, Sx - sx), a1 = a0 + Loom.turn(a0, a);
            // A polar curve that leaves its paper along the radius and arrives along it.
            var pol = Loom.polarBezier([a0, r0], [a0, r0 + (1.24 * sr - r0) * 0.55], [a1, r0 + (1.24 * sr - r0) * 0.45], [a1, 1.24 * sr], 4);
            var pts = Loom.polarXY(sx, sy, pol);
            var obs = obstacles.filter(function (o) { return ends.indexOf(o) < 0 && !insideBox(pts[0], o) && !insideBox(E, o); });
            if (routeIntrusion(pts, obs) > 0) pts = shortestWay(pts[0], E, obs) || pts;
            var ways = fb[2] === 3 ? ['cites', 'cited'] : fb[2] === 1 ? ['cites'] : ['cited'];
            ways.forEach(function (ink, n) {
              var off = ways.length > 1 ? (n ? 1.3 : -1.3) : 0;
              routes.push({ ink: ink, dash: false, w: 1.3, end: true, pts: offsetLine(pts, off) });
            });
          });
        });
        routeCache = { key: sig, routes: routes.map(function (r) {
          return { ink: r.ink, dash: r.dash, w: r.w, end: r.end, pair: r.pair, rel: r.pts.map(function (p) { return [p[0] - sx, p[1] - sy]; }) };
        }) };
      }
      ctx.save();
      // Pointing at a result or a Lean statement brightens its threads; the rest step back.
      var lit = [hover, sel].filter(function (k) { return k && /^[rl]:/.test(k); });
      var anyLit = lit.length && routes.some(function (r) { return r.pair && (lit.indexOf(r.pair[0]) >= 0 || lit.indexOf(r.pair[1]) >= 0); });
      routes.forEach(function (r) {
        var on = r.pair && (lit.indexOf(r.pair[0]) >= 0 || lit.indexOf(r.pair[1]) >= 0);
        ctx.globalAlpha = openA * (anyLit && r.pair ? (on ? 1 : 0.4) : 1);
        ctx.strokeStyle = r.ink === 'steel' ? palette.steel : r.ink === 'cites' ? palette.cites : palette.cited;
        ctx.lineWidth = on ? 1.9 : r.w;
        ctx.setLineDash(r.dash ? [3, 3] : []);
        ctx.beginPath();
        r.pts.forEach(function (p, i) { if (i) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]); });
        ctx.stroke();
      });
      ctx.setLineDash([]);
      ctx.globalAlpha = openA;
      // The fibre's end: a small open ring at the edge.
      (L.fibres[fi] || []).forEach(function (fb) {
        var a = fb[0], ex = sx + 1.24 * sr * Math.cos(a), ey = sy + 1.24 * sr * Math.sin(a);
        ctx.beginPath(); ctx.arc(ex, ey, 3.2, 0, TAU);
        ctx.fillStyle = palette.ground; ctx.fill();
        ctx.lineWidth = 1.2; ctx.strokeStyle = fb[2] & 1 ? palette.cites : palette.cited; ctx.stroke();
      });
      ctx.restore();
      plan.lines = routes;
    }
    function clampAngle(a, lo, hi) {
      var mid = (lo + hi) / 2, d = Loom.turn(mid, a), half = (hi - lo) / 2;
      return mid + clamp(d, -half, half);
    }
    function offsetLine(pts, off) {
      if (!off) return pts;
      return pts.map(function (p, i) {
        var a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
        var dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
        return [p[0] - dy / l * off, p[1] + dx / l * off];
      });
    }
    function trimEnds(pts, r0, r1) {
      if (pts.length < 2) return pts;
      var out = pts.slice();
      var cut = function (a, b, r) {
        var d = Math.hypot(b[0] - a[0], b[1] - a[1]);
        if (d <= r) return a;
        return [a[0] + (b[0] - a[0]) * r / d, a[1] + (b[1] - a[1]) * r / d];
      };
      out[0] = cut(out[0], out[1], r0);
      out[out.length - 1] = cut(out[out.length - 1], out[out.length - 2], r1);
      return out;
    }

    /* ---- The way round words (the Plectis universe's shortestWay) ---------- */
    function segLength(a, b) { return Math.sqrt((b[0] - a[0]) * (b[0] - a[0]) + (b[1] - a[1]) * (b[1] - a[1])); }
    function clipSegment(p, q, b) {
      var dx = q[0] - p[0], dy = q[1] - p[1], t0 = 0, t1 = 1;
      var checks = [[-dx, p[0] - b.x0], [dx, b.x1 - p[0]], [-dy, p[1] - b.y0], [dy, b.y1 - p[1]]];
      for (var c = 0; c < 4; c++) {
        var pp = checks[c][0], qq = checks[c][1];
        if (pp === 0) { if (qq < 0) return null; continue; }
        var t = qq / pp;
        if (pp < 0) { if (t > t0) t0 = t; } else if (t < t1) t1 = t;
        if (t1 < t0) return null;
      }
      return t1 > t0 ? [t0, t1] : null;
    }
    function routeIntrusion(points, obstacles) {
      var inside = 0;
      for (var j = 1; j < points.length; j++) {
        var p = points[j - 1], q = points[j], len = segLength(p, q);
        for (var o = 0; o < obstacles.length; o++) {
          var hit = clipSegment(p, q, obstacles[o]);
          if (hit) inside += (hit[1] - hit[0]) * len;
        }
      }
      return inside;
    }
    function insideBox(pt, b) { return pt[0] > b.x0 && pt[0] < b.x1 && pt[1] > b.y0 && pt[1] < b.y1; }
    var ROUTE_ROUND = 12, ROUTE_GAP = 8;
    function roundRoute(pts) {
      if (pts.length < 3) return pts;
      var out = [pts[0]];
      for (var j = 1; j < pts.length - 1; j++) {
        var p = pts[j - 1], c = pts[j], q = pts[j + 1];
        var r = Math.min(ROUTE_ROUND, segLength(p, c) / 2, segLength(c, q) / 2);
        var lin = segLength(p, c) || 1, lout = segLength(c, q) || 1;
        var s0 = [c[0] + (p[0] - c[0]) * r / lin, c[1] + (p[1] - c[1]) * r / lin];
        var s1 = [c[0] + (q[0] - c[0]) * r / lout, c[1] + (q[1] - c[1]) * r / lout];
        out.push(s0);
        for (var k = 1; k < 6; k++) {
          var t = k / 6, u = 1 - t;
          out.push([u * u * s0[0] + 2 * u * t * c[0] + t * t * s1[0], u * u * s0[1] + 2 * u * t * c[1] + t * t * s1[1]]);
        }
        out.push(s1);
      }
      out.push(pts[pts.length - 1]);
      return out;
    }
    function shortestWay(A, B, obstacles) {
      var route = [A, B];
      if (routeIntrusion(route, obstacles) > 0) {
        route = null;
        var pts = [A, B];
        obstacles.forEach(function (o) {
          [[o.x0 - ROUTE_GAP, o.y0 - ROUTE_GAP], [o.x1 + ROUTE_GAP, o.y0 - ROUTE_GAP],
           [o.x1 + ROUTE_GAP, o.y1 + ROUTE_GAP], [o.x0 - ROUTE_GAP, o.y1 + ROUTE_GAP]].forEach(function (c) {
            if (!obstacles.some(function (other) { return insideBox(c, other); })) pts.push(c);
          });
        });
        var count = pts.length, dist = [], prev = [], done = [];
        for (var n0 = 0; n0 < count; n0++) { dist.push(Infinity); prev.push(-1); done.push(false); }
        dist[0] = 0;
        var clear = function (p, r) {
          var len = segLength(p, r);
          for (var o = 0; o < obstacles.length; o++) {
            var hit = clipSegment(p, r, obstacles[o]);
            if (hit && (hit[1] - hit[0]) * len > 0.5) return false;
          }
          return true;
        };
        for (;;) {
          var at = -1;
          for (var m = 0; m < count; m++) if (!done[m] && (at < 0 || dist[m] < dist[at])) at = m;
          if (at < 0 || !isFinite(dist[at]) || at === 1) break;
          done[at] = true;
          for (var v = 0; v < count; v++) {
            if (done[v]) continue;
            var d = dist[at] + segLength(pts[at], pts[v]) + 10;
            if (d < dist[v] && clear(pts[at], pts[v])) { dist[v] = d; prev[v] = at; }
          }
        }
        if (isFinite(dist[1])) {
          var way = [], step = 1;
          while (step >= 0) { way.unshift(pts[step]); step = prev[step]; }
          route = roundRoute(way);
        }
      }
      return route;
    }

    /* ---- Drawing the words ----------------------------------------------- */
    function drawLines(lines, x, y, font, color, lead, align) {
      ctx.font = font; ctx.fillStyle = color; ctx.textAlign = align || 'left'; ctx.textBaseline = 'middle';
      lines.forEach(function (l, i) { ctx.fillText(l, x, y + lead / 2 + i * lead); });
    }
    function discLeader(q) {
      var lx = q.side > 0 ? q.x0 : q.x1, ly = q.y0 + 8;
      if (Math.abs(lx - q.ax) <= 14 && Math.abs(ly - q.ay) <= 6) return null;
      var ex = lx - q.side * 4;
      return [[q.ax, q.ay], [ex - q.side * 6, ly], [ex, ly]];
    }
    function paintLabels(plan) {
      ctx.save();
      // Discipline names, each with its leader from its sector.
      plan.disc.forEach(function (q) {
        ctx.globalAlpha = q.alpha;
        var lead = discLeader({ side: q.side, x0: q.box.x0, x1: q.box.x1, y0: q.box.y0, ax: q.ax, ay: q.ay });
        if (lead) {
          ctx.strokeStyle = palette.structFaint; ctx.lineWidth = 0.8;
          ctx.beginPath(); ctx.moveTo(lead[0][0], lead[0][1]);
          ctx.lineTo(lead[1][0], lead[1][1]); ctx.lineTo(lead[2][0], lead[2][1]); ctx.stroke();
        }
        var align = q.side > 0 ? 'left' : 'right', x = q.side > 0 ? q.x : q.x + q.t.w;
        drawLines(q.t.lines, x, q.y, DISC_FONT, q.hot ? palette.focus : palette.ink, DISC_LEAD, align);
        drawLines([q.t.count], x, q.y + q.t.lines.length * DISC_LEAD + 1, DISC_COUNT_FONT, palette.muted, 14, align);
      });
      // Family names along their radius.
      var hk = hover ? obj(hover) : null;
      plan.names.forEach(function (n) {
        ctx.globalAlpha = n.alpha;
        var right = Math.cos(n.a) >= 0, hot = hk && famOf(hk) === n.fi;
        if (n.lead) {
          ctx.strokeStyle = hot ? palette.focus : palette.structFaint; ctx.lineWidth = hot ? 1.1 : 0.8;
          ctx.beginPath();
          n.lead.forEach(function (p, i) { if (i) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]); });
          ctx.stroke();
        }
        ctx.save();
        ctx.translate(view.tx + n.r0 * Math.cos(n.a), view.ty + n.r0 * Math.sin(n.a));
        ctx.rotate(right ? n.a : n.a + Math.PI);
        var h = n.t.lines.length * NAME_LEAD;
        drawLines(n.t.lines, 0, -h / 2, NAME_FONT, hot ? palette.focus : palette.muted, NAME_LEAD, right ? 'left' : 'right');
        ctx.restore();
      });
      // The open family's words.
      plan.open.forEach(function (it) {
        ctx.globalAlpha = it.alpha;
        if (it.kind === 'end' && it.t) {
          var hot = hk && hk.kind === 'f' && hk.i === it.g;
          drawLines(it.t.lines, it.right ? it.box.x0 : it.box.x1, it.box.y0, END_FONT, hot ? palette.focus : palette.ink, NAME_LEAD, it.right ? 'left' : 'right');
        } else if (it.kind === 'paper') {
          drawLines(it.t.lines, (it.box.x0 + it.box.x1) / 2, it.box.y0, PAPER_FONT, palette.ink, 16, 'center');
        } else if (it.kind === 'lean') {
          drawLines([it.text], it.box.x0, it.box.y0, LEAN_FONT, palette.steel, 14, 'left');
        } else if (it.kind === 'num') {
          drawLines([it.text], (it.box.x0 + it.box.x1) / 2, it.box.y0, NUM_FONT, palette.muted, 13, 'center');
        } else if (it.kind === 'cap') {
          drawLines([it.text], (it.box.x0 + it.box.x1) / 2, it.box.y0, CAP_FONT, palette.faint, 14, 'center');
        }
      });
      ctx.restore();
    }
    function paintPlates(plan) {
      ctx.save();
      plan.plates.forEach(function (p) {
        var b = p.box;
        if (p.leader) {
          ctx.strokeStyle = palette.focus; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(p.leader[0], p.leader[1]); ctx.lineTo(p.leader[2], p.leader[3]); ctx.stroke();
        }
        ctx.fillStyle = palette.plate; ctx.strokeStyle = palette.plateRule; ctx.lineWidth = 1;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(b.x0 + 0.5, b.y0 + 0.5, b.x1 - b.x0 - 1, b.y1 - b.y0 - 1, 5);
        else ctx.rect(b.x0 + 0.5, b.y0 + 0.5, b.x1 - b.x0 - 1, b.y1 - b.y0 - 1);
        ctx.fill(); ctx.stroke();
        drawLines(p.t.main.lines, b.x0 + p.pad, b.y0 + p.pad - 1, PLATE_FONT, palette.ink, PLATE_LEAD, 'left');
        if (p.t.sub) drawLines(p.t.sub.lines, b.x0 + p.pad, b.y0 + p.pad + p.t.main.lines.length * PLATE_LEAD + 1, PLATE_SUB, palette.muted, 15, 'left');
      });
      ctx.restore();
    }

    /* ---- Hit testing ---------------------------------------------------- */
    function hitAt(x, y) {
      for (var i = hitTargets.length - 1; i >= 0; i--) {
        var h = hitTargets[i];
        if (x >= h.box.x0 && x <= h.box.x1 && y >= h.box.y0 && y <= h.box.y1) return h.key;
      }
      var k = view.k, openF = openFamily();
      if (openF >= 0 && screenR(openF) > 50) {
        var f = fams[openF], sx = f.x * k + view.tx, sy = f.y * k + view.ty, sr = f.r * k;
        var best = null, bd = Math.max(8, dotRadius(sr) * 1.6 + 3);
        f.data.papers.forEach(function (pi) {
          D.papers[pi].results.forEach(function (ri) {
            var p = L.results[ri], d = Math.hypot(sx + p[0] * sr - x, sy + p[1] * sr - y);
            if (d < bd) { bd = d; best = D.results[ri].id; }
          });
        });
        f.data.lean.forEach(function (li) {
          var p = L.lean[li], d = Math.hypot(sx + p[0] * sr - x, sy + p[1] * sr - y);
          if (d < bd) { bd = d; best = D.lean[li].id; }
        });
        if (best) return best;
        // A paper's ring or arc, within a few pixels of its line.
        for (var q = 0; q < f.data.papers.length; q++) {
          var pi = f.data.papers[q], g = L.papers[pi];
          var dx = x - (sx + g[0] * sr), dy = y - (sy + g[1] * sr), rr = Math.hypot(dx, dy);
          if (Math.abs(rr - g[2] * sr) > 6) continue;
          var a = Math.atan2(dy, dx), whole = g[4] - g[3] >= TAU - 1e-3;
          if (whole || Math.abs(Loom.turn((g[3] + g[4]) / 2, a)) <= (g[4] - g[3]) / 2) return D.papers[pi].id;
        }
        var dc = Math.hypot(x - sx, y - sy);
        if (dc < sr * 1.05) return D.families[openF].id;
        if (screenR(openF) > Math.min(W, H) * 0.25) return null;
      }
      // A family's small map.
      var bestF = -1, bestD = Infinity;
      for (var fi = 0; fi < fams.length; fi++) {
        var fm = fams[fi], d2 = Math.hypot(fm.x * k + view.tx - x, fm.y * k + view.ty - y), rr2 = fm.r * k + 3;
        if (d2 <= rr2 && d2 / rr2 < bestD) { bestD = d2 / rr2; bestF = fi; }
      }
      if (bestF >= 0 && (openF < 0 || bestF === openF || 1 - smooth((screenR(openF) - 80) / 110) > 0.3)) return D.families[bestF].id;
      // A sector of the wheel.
      var wx = (x - view.tx) / k, wy = (y - view.ty) / k, wr = Math.hypot(wx, wy), wa = Math.atan2(wy, wx);
      if (openF < 0 && wr >= L.wheel.rIn * 0.95) {
        for (var di = 0; di < L.wheel.sectors.length; di++) {
          var s = L.wheel.sectors[di];
          if (wr <= s[3] + 2 && Math.abs(Loom.turn((s[0] + s[1]) / 2, wa)) <= (s[1] - s[0]) / 2) return D.disciplines[di].id;
        }
      }
      return null;
    }

    /* ---- Selection, trail and address ------------------------------------- */
    function parentKey(o) {
      if (!o) return null;
      if (o.kind === 'd') return null;
      if (o.kind === 'f') return D.disciplines[fams[o.i].d].id;
      return D.families[famOf(o)].id;
    }
    function updateHash() {
      if (!window.history || !window.history.replaceState) return;
      var base = window.location.pathname + window.location.search;
      window.history.replaceState(null, '', sel ? base + '#o=' + encodeURIComponent(sel) : base);
    }
    // Select an object: its panel, its plate and, where its level asks, a flight.
    function select(key, opts) {
      opts = opts || {};
      var o = key ? obj(key) : null;
      if (key && !o) return;
      var before = viewNow();
      var prev = sel ? obj(sel) : null;
      sel = key || null;
      hover = null;
      routeCache.key = '';
      if (opts.trail) trail.push({ key: key, before: before, prev: prev ? prev.key : null });
      renderPanel();
      updateHash();
      if (o && liveEl) liveEl.textContent = nameOf(o);
      var fly = opts.fly !== false;
      if (fly) {
        var needs = !o || o.kind === 'd' || o.kind === 'f' || famOf(o) !== famOf(prev) || !inView(o);
        if (needs) cameraTo(frameFor(o), !o, opts.delay);
        else draw();
      } else draw();
    }
    function inView(o) {
      var p = objPos(o);
      var x = p[0] * view.k + view.tx, y = p[1] * view.k + view.ty;
      return x > 40 && x < W - 40 && y > 40 && y < H - 40 && screenR(famOf(o)) > 90;
    }
    function stepBack() {
      if (trail.length) {
        var last = trail.pop();
        sel = last.prev;
        hover = null;
        routeCache.key = '';
        renderPanel();
        updateHash();
        if (last.before.fitted) cameraTo(fitView(), true);
        else cameraTo({ k: last.before.k, tx: last.before.tx, ty: last.before.ty }, false);
        return;
      }
      if (sel) { select(parentKey(obj(sel)), {}); return; }
      if (!viewFitted) cameraTo(fitView(), true);
    }
    function openPage(o) {
      if (!o) return;
      var href = null;
      if (o.kind === 'f') href = D.families[o.i].href;
      else if (o.kind === 'p') href = D.papers[o.i].href || D.papers[o.i].pdf;
      else if (o.kind === 'r') href = D.results[o.i].href || D.papers[D.results[o.i].p].href || D.papers[D.results[o.i].p].pdf;
      else if (o.kind === 'l') href = D.lean[o.i].href;
      if (href) window.location.href = href;
    }

    /* ---- Panel ------------------------------------------------------------ */
    function goBtn(key, inner, cls) {
      return '<button type="button" class="u-go ' + (cls || '') + '" data-go="' + escapeHtml(key) + '">' + inner + '</button>';
    }
    function leanGlyph(n, holes) {
      var fills = ['u-sw-lean0', 'u-sw-lean1', 'u-sw-lean2', 'u-sw-lean3'];
      return '<svg class="u-sw ' + fills[n] + (holes ? ' u-sw-holes' : '') + '" viewBox="0 0 14 14" aria-hidden="true"><path d="M7 1.6 12.4 7 7 12.4 1.6 7Z"/>' +
        (holes ? '<circle cx="7" cy="7" r="1.8" class="u-sw-hole"/>' : '') + '</svg>';
    }
    function resultGlyph(paired) {
      return '<svg class="u-sw ' + (paired ? 'u-sw-paired' : 'u-sw-unpaired') + '" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="4"/></svg>';
    }
    function trailHtml() {
      var o = sel ? obj(sel) : null, items = [];
      var chain = [];
      for (var c = o; c; c = obj(parentKey(c))) chain.unshift(c);
      if (!o) return '';
      items.push(goBtn('', escapeHtml(T('levels.release')), 'u-crumb'));
      chain.forEach(function (c, i) {
        var label = c.kind === 'f' ? D.families[c.i].title : c.kind === 'd' ? D.disciplines[c.i].name :
          c.kind === 'r' ? resultName(D.results[c.i]) : c.kind === 'l' ? D.lean[c.i].name : T('levels.paper');
        if (i < chain.length - 1) items.push(goBtn(c.key, escapeHtml(label), 'u-crumb'));
      });
      return items.join('<span class="u-crumb-sep" aria-hidden="true">/</span>');
    }
    function renderPanel() {
      if (!viewEl) return;
      var o = sel ? obj(sel) : null;
      if (trailEl) trailEl.innerHTML = trailHtml();
      if (trailEl) trailEl.hidden = !o;
      var groundEl = root.querySelector('[data-u-ground]');
      if (groundEl) groundEl.hidden = !!o;
      var html = '';
      if (!o) html = releaseHtml();
      else if (o.kind === 'd') html = disciplineHtml(o.i);
      else if (o.kind === 'f') html = familyHtml(o.i);
      else if (o.kind === 'p') html = paperHtml(o.i);
      else if (o.kind === 'r') html = resultHtml(o.i);
      else if (o.kind === 'l') html = leanHtml(o.i);
      if (titleEl) titleEl.textContent = o ? nameOf(o) : T('page.title');
      if (titleEl) titleEl.className = 'u-title' + (o && o.kind === 'l' ? ' u-title--code' : '') + (o ? ' u-title--deep' : '');
      viewEl.innerHTML = html;
      if (panelBody) panelBody.scrollTop = 0;
      typeset(viewEl, o);
      if (o) {
        var di = discOf(o);
        if (di >= 0 && !shards[di]) loadShard(di).then(function () { if (sel === (o && o.key)) { viewEl.innerHTML = rerender(o); typeset(viewEl, o); } }, function () {});
      }
    }
    function rerender(o) {
      if (o.kind === 'f') return familyHtml(o.i);
      if (o.kind === 'r') return resultHtml(o.i);
      if (o.kind === 'l') return leanHtml(o.i);
      if (o.kind === 'p') return paperHtml(o.i);
      if (o.kind === 'd') return disciplineHtml(o.i);
      return releaseHtml();
    }
    function loadShard(di) {
      if (shards[di]) return Promise.resolve(shards[di]);
      if (shardLoading[di]) return shardLoading[di];
      var url = root.getAttribute('data-universe-detail').replace('{d}', di);
      shardLoading[di] = fetchJson(url).then(function (sh) {
        if (sh.generation_id !== D.generation_id) throw new Error('detail from another build');
        shards[di] = sh;
        return sh;
      }, function (err) { shardLoading[di] = null; throw err; });
      return shardLoading[di];
    }
    function detail(o) {
      var sh = shards[discOf(o)];
      if (!sh) return null;
      if (o.kind === 'r') return sh.results[o.key];
      if (o.kind === 'l') return sh.lean[o.key];
      if (o.kind === 'f') return sh.families[o.key];
      return null;
    }
    function typeset(el, o) {
      if (!window.katex) { if (window.atlasRenderMath) window.atlasRenderMath(el); return; }
      var macros = {}, k;
      for (k in GLOBAL_MACROS) macros[k] = GLOBAL_MACROS[k];
      var sh = o ? shards[discOf(o)] : null;
      if (sh && o.kind === 'r') {
        var own = sh.macros[D.papers[D.results[o.i].p].id] || {};
        for (k in own) {
          var v = own[k];
          if (typeof v === 'string' && !/\\(?:newcommand|def|let|ifx|ifmmode|csname|expandafter)/.test(v)) macros[k] = v;
        }
      }
      var spans = el.querySelectorAll('span.m:not([data-done])');
      for (var i = 0; i < spans.length; i++) {
        var s = spans[i], tex = s.textContent;
        s.setAttribute('data-done', '1');
        try {
          window.katex.render(tex, s, { displayMode: s.getAttribute('data-d') === '1', macros: macros, throwOnError: true, strict: 'ignore', trust: false, maxExpand: 2000 });
        } catch (err) { s.textContent = tex; s.classList.add('m-fail'); }
      }
      if (window.atlasRenderMath) window.atlasRenderMath(el);
    }
    function legendHtml() {
      var acc = [0, 0, 0, 0], holes = 0, paired = 0, hol = 0, fin = 0;
      D.lean.forEach(function (l) { acc[l.acc.length]++; if (l.holes) holes++; });
      D.results.forEach(function (r) { if (r.lean.length) paired++; });
      D.families.forEach(function (f) { if (f.hol) hol++; if (f.fin) fin++; });
      var groups = Object.keys(D.sources).filter(function (s) { return D.lean.some(function (l) { return l.acc.indexOf(s) >= 0; }); })
        .map(function (s) { return D.sources[s]; });
      var row = function (glyph, text, n) {
        return '<li><span class="u-key__g">' + glyph + '</span><span class="u-key__t">' + escapeHtml(text) + '</span>' +
          (n == null ? '' : '<span class="u-key__n">' + fmtNum(n) + '</span>') + '</li>';
      };
      var ring = function (cls) { return '<svg class="u-sw ' + cls + '" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.4"/></svg>'; };
      var fib = function (cls) { return '<svg class="u-sw ' + cls + '" viewBox="0 0 14 14" aria-hidden="true"><path d="M1 10 C5 10 9 4 13 4"/></svg>'; };
      return '<p class="u-note">' + escapeHtml(T('legend.colour_note')) + '</p>' +
        '<h3 class="u-h3">' + escapeHtml(T('legend.lean_heading')) + '</h3><ul class="u-key">' +
        row(leanGlyph(3), T('legend.lean_3'), acc[3]) + row(leanGlyph(2), T('legend.lean_2'), acc[2]) +
        row(leanGlyph(1), T('legend.lean_1'), acc[1]) + row(leanGlyph(0), T('legend.lean_0'), acc[0]) +
        row(leanGlyph(2, true), T('legend.lean_holes'), holes) + '</ul>' +
        '<p class="u-note">' + escapeHtml(T('legend.lean_groups', { groups: groups.join('; ') })) + '</p>' +
        '<h3 class="u-h3">' + escapeHtml(T('legend.result_heading')) + '</h3><ul class="u-key">' +
        row(resultGlyph(true), T('legend.result_paired'), paired) + row(resultGlyph(false), T('legend.result_unpaired'), D.results.length - paired) + '</ul>' +
        '<p class="u-note">' + escapeHtml(T('legend.pair_note')) + '</p>' +
        '<h3 class="u-h3">' + escapeHtml(T('legend.family_heading')) + '</h3><ul class="u-key">' +
        row(ring('u-sw-hol'), T('legend.family_hol'), hol) + row(ring('u-sw-fin'), T('legend.family_finite'), fin) + '</ul>' +
        '<h3 class="u-h3">' + escapeHtml(T('legend.fibre_heading')) + '</h3><ul class="u-key">' +
        row(fib('u-sw-cites'), T('legend.fibre_cites')) + row(fib('u-sw-cited'), T('legend.fibre_cited')) + '</ul>' +
        '<p class="u-note">' + escapeHtml(T('legend.fibre_note')) + '</p>';
    }
    function releaseHtml() {
      var rows = D.disciplines.map(function (d) {
        return '<li>' + goBtn(d.id, '<span class="u-row__t">' + escapeHtml(d.name) + '</span><span class="u-row__n">' +
          escapeHtml(count('families', d.families.length)) + '</span>', 'u-row') + '</li>';
      }).join('');
      return restViewHtml;
    }
    function famRow(fi) {
      var f = D.families[fi];
      return '<li>' + goBtn(f.id, '<span class="u-row__t">' + escapeHtml(f.title) +
        '</span><span class="u-row__n">' + escapeHtml(count('results', f.papers.reduce(function (s, p) { return s + D.papers[p].results.length; }, 0))) +
        (f.lean.length ? ' and ' + escapeHtml(count('lean', f.lean.length)) : '') + '</span>', 'u-row') + '</li>';
    }
    function disciplineHtml(di) {
      var d = D.disciplines[di];
      var out = 0, inn = 0;
      D.links.forEach(function (row) {
        var da = fams[row[0]].d, db = fams[row[1]].d;
        if (da === db) return;
        if (da === di) { out += row[2]; inn += row[3]; }
        if (db === di) { out += row[3]; inn += row[2]; }
      });
      return '<p class="u-kicker">' + escapeHtml(T('discipline.kicker')) + '</p>' +
        '<p class="u-facts">' + escapeHtml(T('counts.families_in', { families: count('families', d.families.length), papers: count('papers', d.papers), results: count('results', d.results), lean: count('lean', d.lean) })) + '</p>' +
        '<p class="u-note">' + escapeHtml(T('discipline.connections', { out: out, 'in': inn })) + '</p>' +
        '<h2 class="u-h2">' + escapeHtml(T('discipline.families_heading')) + '</h2><ul class="u-rows">' + d.families.map(famRow).join('') + '</ul>';
    }
    function link(href, text, cls) {
      if (!href) return '';
      var ext = /^https?:/.test(href);
      return '<a class="u-link' + (ext ? ' ext' : '') + (cls ? ' ' + cls : '') + '" href="' + escapeHtml(href) + '"' + (ext ? ' rel="noopener"' : '') + '>' + escapeHtml(text) + '</a>';
    }
    function findingsHtml(list, heading) {
      if (!list || !list.length) return '';
      return '<h3 class="u-h3">' + escapeHtml(heading) + '</h3><ul class="u-finds">' + list.map(function (f) {
        return '<li><span class="u-pill">' + escapeHtml(f.kind) + '</span> ' + escapeHtml(f.summary) +
          ' <span class="u-muted">' + escapeHtml([f.who, f.effort].filter(Boolean).join(', ')) + ', ' + escapeHtml(longDate(f.date)) + '.</span> ' +
          link(f.url, T('family.source')) + '</li>';
      }).join('') + '</ul>';
    }
    function familyEvidenceHtml(fi) {
      var f = D.families[fi], det = detail(obj(f.id)), bits = [];
      bits.push('<p><strong>' + escapeHtml(T('family.readers_heading')) + '</strong> ' + escapeHtml(T('family.readers_' + f.readers)) + '</p>');
      if (f.readers !== 'none') bits.push('<p class="u-note">' + escapeHtml(T('family.readers_source')) + '</p>');
      if (f.hol) bits.push('<p>' + escapeHtml(f.hol === 1 ? T('family.hol_one') : T('family.hol', { n: f.hol })) + '</p>');
      if (f.fin) bits.push('<p>' + escapeHtml(f.fin === 1 ? T('family.finite_one') : T('family.finite', { n: f.fin })) +
        (f.finOther ? ' ' + escapeHtml(T('family.finite_other', { n: f.finOther })) : '') + '</p>');
      if (det && det.hol && det.hol.length) bits.push('<ul class="u-checks">' + det.hol.map(function (h) { return '<li>' + escapeHtml(h.text) + ' ' + link(h.url, T('family.hol_card', { card: h.card })) + '</li>'; }).join('') + '</ul>');
      return '<div class="u-evidence">' + bits.join('') + '</div>';
    }
    function familyHtml(fi) {
      var f = D.families[fi], det = detail(obj(f.id));
      var nRes = f.papers.reduce(function (s, p) { return s + D.papers[p].results.length; }, 0);
      var h = '<p class="u-kicker">' + escapeHtml(T('family.kicker', { num: f.num, discipline: D.disciplines[f.d].name })) + '</p>';
      h += '<p class="u-facts">' + escapeHtml(T('counts.papers_with', { papers: count('papers', f.papers.length), results: count('results', nRes), lean: f.lean.length ? count('lean', f.lean.length) : T('counts.lean_none') })) + '</p>';
      h += '<p class="u-doors">' + link(f.href, T('family.page_link')) + '</p>';
      if (det) h += '<div class="u-desc tex-auto">' + det.description + '</div>';
      h += familyEvidenceHtml(fi);
      h += '<h2 class="u-h2">' + escapeHtml(T('family.papers_heading')) + '</h2><ol class="u-papers">';
      f.papers.forEach(function (pi, n) {
        var p = D.papers[pi];
        h += '<li>' + goBtn(p.id, '<span class="u-row__t">' + escapeHtml(p.title) + '</span>' + (n === 0 && f.papers.length > 1 ? '<span class="u-row__n">' + escapeHtml(T('family.lead')) + '</span>' : ''), 'u-row u-row--paper');
        if (p.results.length) {
          h += '<ul class="u-subrows">' + p.results.map(function (ri) {
            var r = D.results[ri];
            return '<li>' + goBtn(r.id, resultGlyph(r.lean.length > 0) + '<span>' + escapeHtml(resultName(r) + (r.title ? ' (' + r.title + ')' : '')) + '</span>', 'u-sub') + '</li>';
          }).join('') + '</ul>';
        }
        h += '</li>';
      });
      h += '</ol>';
      if (f.lean.length) {
        h += '<h2 class="u-h2">' + escapeHtml(T('family.lean_heading')) + '</h2><ul class="u-subrows">' + f.lean.map(function (li) {
          var l = D.lean[li];
          return '<li>' + goBtn(l.id, leanGlyph(l.acc.length, l.holes) + '<code>' + escapeHtml(l.name) + '</code>', 'u-sub') + '</li>';
        }).join('') + '</ul>';
      }
      h += '<h2 class="u-h2">' + escapeHtml(T('family.connections_heading')) + '</h2>';
      if (!f.cites.length && !f.citedBy.length) h += '<p class="u-note">' + escapeHtml(T('family.no_connections')) + '</p>';
      [['cites', f.cites, 'u-sw-cites'], ['cited_by', f.citedBy, 'u-sw-cited']].forEach(function (part) {
        if (!part[1].length) return;
        h += '<h3 class="u-h3">' + escapeHtml(T('family.' + part[0])) + '</h3><ul class="u-rows">' + part[1].map(function (c) {
          var g = D.families[c[0]];
          return '<li>' + goBtn(g.id, '<svg class="u-sw ' + part[2] + '" viewBox="0 0 14 14" aria-hidden="true"><path d="M1 10 C5 10 9 4 13 4"/></svg><span class="u-row__t">' + escapeHtml(g.title) + '</span><span class="u-row__n">' + escapeHtml(count('links', c[1])) + '</span>', 'u-row u-row--link') + '</li>';
        }).join('') + '</ul>';
      });
      if (det) h += findingsHtml(det.findings, T('family.findings_heading'));
      return h;
    }
    function paperHtml(pi) {
      var p = D.papers[pi], f = D.families[p.f];
      var h = '<p class="u-kicker">' + escapeHtml(T('paper.kicker', { num: f.num })) + '</p>';
      h += '<p class="u-doors">' + link(p.href, T('paper.read')) + link(p.pdf, T('paper.pdf')) + '</p>';
      h += '<h2 class="u-h2">' + escapeHtml(T('paper.results_heading')) + '</h2>';
      if (!p.results.length) h += '<p class="u-note">' + escapeHtml(T('paper.no_results')) + '</p>';
      else h += '<ul class="u-subrows">' + p.results.map(function (ri) {
        var r = D.results[ri];
        return '<li>' + goBtn(r.id, resultGlyph(r.lean.length > 0) + '<span>' + escapeHtml(resultName(r) + (r.title ? ' (' + r.title + ')' : '')) + '</span>', 'u-sub') + '</li>';
      }).join('') + '</ul>';
      return h;
    }
    function resultHtml(ri) {
      var r = D.results[ri], p = D.papers[r.p], f = D.families[r.f], o = obj(r.id), det = detail(o);
      var h = '<p class="u-context">' + escapeHtml(T('result.in_paper_lead')) + ' ' + goBtn(p.id, escapeHtml(p.title), 'u-inline u-inline--plain') + '</p>';
      if (det) {
        h += '<figure class="u-stmt"><div class="u-stmt__body">' + det.html + '</div><figcaption class="u-note">' + escapeHtml(det.where) + '</figcaption></figure>';
      } else {
        h += '<p class="u-note" data-u-loading>' + escapeHtml(shardLoading[discOf(o)] === null ? T('result.load_failed') : T('result.loading')) + '</p>';
      }
      h += '<p class="u-doors">' + link(r.href || p.href || p.pdf, T('result.read'));
      r.lean.forEach(function (li) { h += link(D.lean[li].href, T('result.lean_page') + ': ' + D.lean[li].name); });
      h += link(f.href, T('result.family_page')) + '</p>';
      h += '<p class="u-note">' + escapeHtml(r.num ? T('result.numbering_note') : r.nn ? T('result.unnumbered') : T('result.number_unavailable')) + '</p>';
      h += '<h2 class="u-h2">' + escapeHtml(T('result.evidence_heading')) + '</h2>';
      if (r.lean.length) {
        h += '<p>' + escapeHtml(T('result.paired', { names: r.lean.map(function (li) { return D.lean[li].name; }).join(', ') })) + '</p><ul class="u-subrows">' +
          r.lean.map(function (li) { var l = D.lean[li]; return '<li>' + goBtn(l.id, leanGlyph(l.acc.length, l.holes) + '<code>' + escapeHtml(l.name) + '</code>', 'u-sub') + '</li>'; }).join('') + '</ul>';
      } else h += '<p>' + escapeHtml(T('result.unpaired')) + '</p>';
      h += '<p class="u-h3">' + escapeHtml(T('result.family_evidence')) + ' ' + goBtn(f.id, escapeHtml(T('family.short', { num: f.num })), 'u-inline') + '</p>';
      h += familyEvidenceHtml(r.f);
      var fd = detail(obj(f.id));
      if (fd) h += findingsHtml(fd.findings, T('result.findings_heading'));
      return h;
    }
    function leanHtml(li) {
      var l = D.lean[li], f = D.families[l.f], det = detail(obj(l.id));
      var h = '<p class="u-kicker">' + escapeHtml(T('lean.kicker', { num: f.num })) + '</p>';
      h += '<p class="u-lean-label">' + escapeHtml(l.label) + '</p>';
      if (l.main) h += '<p class="u-note">' + escapeHtml(T('lean.main')) + '</p>';
      if (det && det.snippet) h += '<pre class="lean lean--snippet u-lean"><code>' + det.snippet + '</code></pre>';
      h += '<p class="u-doors">' + link(l.href, T('lean.page')) + link(f.href, T('lean.family_page')) + '</p>';
      h += '<h2 class="u-h2">' + escapeHtml(T('lean.reruns_heading')) + '</h2>';
      if (det) {
        if (!det.reruns.length) h += '<p class="u-note">' + escapeHtml(T('lean.reruns_none')) + '</p>';
        else h += '<ul class="u-reruns">' + det.reruns.map(function (x) {
          var ok = x.verdict === 'accepted';
          return '<li class="' + (ok ? 'is-ok' : 'is-not') + '"><strong>' + escapeHtml(D.sources[x.source] || x.source) + '</strong>: ' +
            escapeHtml((COPY.lean && COPY.lean.verdicts && COPY.lean.verdicts[x.verdict]) || (ok ? T('lean.accepted') : T('lean.not_accepted'))) + (x.date ? ', ' + escapeHtml(longDate(x.date)) : '') + '. ' +
            '<span class="u-muted">' + escapeHtml(x.text || '') + '</span> ' + link(x.url, T('lean.record')) + '</li>';
        }).join('') + '</ul>';
        if (det.holes.length) h += '<h3 class="u-h3">' + escapeHtml(T('lean.holes_heading')) + '</h3><p class="u-note">' + escapeHtml(T('lean.holes_note')) + '</p><p>' +
          det.holes.map(function (n) { return '<code>' + escapeHtml(n) + '</code>'; }).join(', ') + '</p>';
      } else {
        h += '<p class="u-note">' + escapeHtml(l.acc.map(function (s) { return D.sources[s]; }).join('; ')) + '</p>';
      }
      h += '<h2 class="u-h2">' + escapeHtml(T('lean.paired_heading')) + '</h2>';
      if (l.results.length) {
        h += '<p class="u-note">' + escapeHtml(T('lean.paired_note')) + '</p><ul class="u-subrows">' + l.results.map(function (ri) {
          var r = D.results[ri];
          return '<li>' + goBtn(r.id, resultGlyph(true) + '<span>' + escapeHtml(resultName(r) + ', ' + D.papers[r.p].title) + '</span>', 'u-sub') + '</li>';
        }).join('') + '</ul>';
      } else h += '<p class="u-note">' + escapeHtml(T('lean.paired_none')) + '</p>';
      if (det) h += findingsHtml(det.findings, T('lean.findings_heading'));
      return h;
    }

    /* ---- Search ----------------------------------------------------------- */
    function loadSearch() {
      if (searchRows) return Promise.resolve(searchRows);
      if (searchLoading) return searchLoading;
      resultsEl.hidden = false;
      resultsEl.innerHTML = '<p class="u-note">' + escapeHtml(T('search.loading')) + '</p>';
      searchLoading = fetchJson(root.getAttribute('data-universe-search')).then(function (s) {
        if (s.generation_id !== D.generation_id) throw new Error('search from another build');
        searchRows = s.rows;
        return searchRows;
      }, function (err) {
        searchLoading = null;
        resultsEl.innerHTML = '<p class="u-note">' + escapeHtml(T('search.failed')) + '</p>';
        throw err;
      });
      return searchLoading;
    }
    var matchList = [];
    function runSearch() {
      var q = (searchIn.value || '').trim().toLowerCase();
      query = q;
      if (!q) {
        matches = null; matchFam = null; matchList = [];
        resultsEl.hidden = true; resultsEl.innerHTML = '';
        draw();
        return;
      }
      loadSearch().then(function (rows) {
        if (query !== q) return;
        var words = q.split(/\s+/).filter(Boolean);
        var found = [];
        rows.forEach(function (row) {
          for (var i = 0; i < words.length; i++) if (row[1].indexOf(words[i]) < 0) return;
          found.push(row[0]);
        });
        var rank = { r: 0, l: 1, f: 2, p: 3 };
        found.sort(function (a, b) { return rank[a[0]] - rank[b[0]]; });
        matchList = found;
        matches = {}; matchFam = {};
        found.forEach(function (key) {
          matches[key] = true;
          var o = obj(key), f = famOf(o);
          if (f >= 0) matchFam[f] = true;
        });
        var shown = found.slice(0, 60);
        var kindWord = { f: T('search.kind_family'), p: T('search.kind_paper'), r: T('search.kind_result'), l: T('search.kind_lean') };
        var head = found.length ? (found.length === 1 ? T('search.count_one') : T('search.count', { n: found.length })) : T('search.none');
        if (found.length > shown.length) head += ' ' + T('search.shown', { shown: shown.length });
        resultsEl.hidden = false;
        resultsEl.innerHTML = '<p class="u-note" role="status">' + escapeHtml(head) + '</p><ul class="u-rows">' + shown.map(function (key) {
          var o = obj(key), f = famOf(o);
          var where = f >= 0 && o.kind !== 'f' ? T('family.short', { num: D.families[f].num }) + ', ' + D.families[f].title : D.disciplines[discOf(o)].name;
          return '<li>' + goBtn(key, '<span class="u-row__k">' + escapeHtml(kindWord[o.kind]) + '</span><span class="u-row__t">' + escapeHtml(nameOf(o)) +
            '</span><span class="u-row__n">' + escapeHtml(where) + '</span>', 'u-row u-row--hit') + '</li>';
        }).join('') + '</ul>';
        draw();
      }, function () {});
    }

    /* ---- Events --------------------------------------------------------- */
    var panning = false, moved = false, px0 = 0, py0 = 0, pointers = {}, pinch = null, lastClick = 0;
    function localXY(e) { var r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
    canvas.addEventListener('pointermove', function (e) {
      if (pinch) return;
      if (panning) {
        var dx = e.clientX - px0, dy = e.clientY - py0;
        if (!moved && dx * dx + dy * dy < 9) return;
        moved = true; viewFitted = false;
        view.tx += dx; view.ty += dy; px0 = e.clientX; py0 = e.clientY;
        if (cameraFrame) { cancelAnimationFrame(cameraFrame); cameraFrame = 0; moving = false; }
        draw();
        return;
      }
      var p = localXY(e), h = hitAt(p[0], p[1]);
      if (h !== hover) {
        hover = h;
        canvas.classList.toggle('is-over', !!h);
        draw();
      }
    });
    canvas.addEventListener('pointerleave', function () {
      if (hover) { hover = null; canvas.classList.remove('is-over'); draw(); }
    });
    canvas.addEventListener('pointerdown', function (e) {
      pointers[e.pointerId] = [e.clientX, e.clientY];
      var ids = Object.keys(pointers);
      if (ids.length === 2) {
        var a = pointers[ids[0]], b = pointers[ids[1]];
        pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), mx: (a[0] + b[0]) / 2, my: (a[1] + b[1]) / 2 };
        panning = false; moved = true;
        return;
      }
      panning = true; moved = false; px0 = e.clientX; py0 = e.clientY;
      canvas.classList.add('is-panning');
      if (canvas.setPointerCapture) canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener('pointermove', function (e) {
      if (!pointers[e.pointerId]) return;
      pointers[e.pointerId] = [e.clientX, e.clientY];
      var ids = Object.keys(pointers);
      if (pinch && ids.length >= 2) {
        var a = pointers[ids[0]], b = pointers[ids[1]], r = canvas.getBoundingClientRect();
        var d = Math.hypot(a[0] - b[0], a[1] - b[1]), mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
        view.tx += mx - pinch.mx; view.ty += my - pinch.my;
        zoomAt(mx - r.left, my - r.top, d / pinch.d);
        pinch = { d: d, mx: mx, my: my };
      }
    });
    var release = function (e) {
      delete pointers[e.pointerId];
      if (Object.keys(pointers).length < 2) pinch = null;
      panning = false;
      canvas.classList.remove('is-panning');
    };
    canvas.addEventListener('pointerup', release);
    canvas.addEventListener('pointercancel', release);
    canvas.addEventListener('click', function (e) {
      if (moved) { moved = false; return; }
      var p = localXY(e), key = hitAt(p[0], p[1]), o = key ? obj(key) : null;
      var now = Date.now();
      // A second click on what is already selected opens it, as a double-click does.
      if (o && (e.detail >= 2 || (key === sel && now - lastClick < 450))) { openPage(o); return; }
      lastClick = now;
      if (!o) { stepBack(); return; }
      if (key === sel) return;
      select(key, { trail: true });
    });
    canvas.addEventListener('dblclick', function (e) {
      var p = localXY(e), key = hitAt(p[0], p[1]);
      if (key) openPage(obj(key));
    });
    // Over the map the wheel zooms about the pointer; a scroll already moving the
    // page carries on (350 ms), and a pinch always zooms.
    var pageWheelAt = -1e9;
    window.addEventListener('wheel', function (e) { if (e.target !== canvas) pageWheelAt = e.timeStamp || Date.now(); }, { passive: true, capture: true });
    canvas.addEventListener('wheel', function (e) {
      var now = e.timeStamp || Date.now();
      if (!e.ctrlKey && !e.metaKey && now - pageWheelAt < 350) { pageWheelAt = now; return; }
      e.preventDefault();
      var p = localXY(e);
      var dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? H : 1);
      dy = clamp(dy, -240, 240);
      zoomAt(p[0], p[1], Math.exp(-dy * (e.ctrlKey ? 0.01 : 0.0022)));
      settleZoom(p[0], p[1]);
    }, { passive: false });
    function zoomAt(mx, my, factor) {
      if (cameraFrame) { cancelAnimationFrame(cameraFrame); cameraFrame = 0; moving = false; }
      var k = clamp(view.k * factor, fitK * 0.6, 900);
      factor = k / view.k;
      viewFitted = false;
      view.tx = mx - (mx - view.tx) * factor;
      view.ty = my - (my - view.ty) * factor;
      view.k = k;
      draw();
    }
    // Zooming is drilling: a family that comes to fill the view opens, and an
    // open family that shrinks back gives way to its discipline, then the release.
    var settleTimer = 0;
    function settleZoom(mx, my) {
      clearTimeout(settleTimer);
      settleTimer = setTimeout(function () {
        var o = sel ? obj(sel) : null, m = Math.min(W, H);
        var openF = famOf(o);
        if (openF >= 0) {
          if (screenR(openF) < m * 0.12) select(view.k < fitK * 1.25 ? null : D.disciplines[fams[openF].d].id, { fly: false });
          return;
        }
        var key = hitAt(mx, my), h = key ? obj(key) : null;
        if (h && h.kind === 'f' && screenR(h.i) > m * 0.3) { select(h.key, { fly: false, trail: true }); return; }
        if (!o && view.k > fitK * 2.4 && h) { var di = discOf(h); if (di >= 0) select(D.disciplines[di].id, { fly: false }); return; }
        if (o && o.kind === 'd' && view.k < fitK * 1.25) select(null, { fly: false });
      }, 160);
    }
    document.addEventListener('click', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      if (!go || !D) return;
      if (e.defaultPrevented || e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      var key = go.getAttribute('data-go');
      if (key && !obj(key)) return;
      e.preventDefault();
      var outside = !root.contains(go);
      var narrow = window.matchMedia && window.matchMedia('(max-width: 899px)').matches;
      // A way in chosen from beside or below the map brings the map into view: the
      // map's own side of the switch on a phone, the top of the page elsewhere.
      if (key && (outside || go.classList.contains('u-way')) && narrow) showView('map');
      // The map is the page's first screen: going back up to it shows the header too.
      if (outside) window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
      select(key || null, { trail: true });
    });
    // A row under the pointer in the panel lights its place on the map.
    root.addEventListener('pointerover', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      var key = go ? go.getAttribute('data-go') : null;
      if (go && panelBody && panelBody.contains(go) && key && key !== hover) { hover = key; draw(); }
    });
    root.addEventListener('pointerout', function (e) {
      var go = e.target.closest ? e.target.closest('[data-go]') : null;
      if (go && panelBody && panelBody.contains(go) && hover === go.getAttribute('data-go')) { hover = null; draw(); }
    });
    root.querySelectorAll('[data-u-zoom]').forEach(function (b) {
      b.addEventListener('click', function () {
        var m = b.getAttribute('data-u-zoom');
        if (m === 'fit') { if (sel) select(null, { trail: true }); else cameraTo(fitView(), true); return; }
        var f = m === 'in' ? 1.5 : 1 / 1.5, k = clamp(view.k * f, fitK * 0.6, 900);
        f = k / view.k;
        cameraTo({ k: k, tx: W / 2 - (W / 2 - view.tx) * f, ty: H / 2 - (H / 2 - view.ty) * f }, false);
        setTimeout(function () { settleZoom(W / 2, H / 2); }, 700);
      });
    });
    function showView(v) {
      root.setAttribute('data-view', v);
      root.querySelectorAll('[data-u-show]').forEach(function (x) { x.setAttribute('aria-pressed', x.getAttribute('data-u-show') === v ? 'true' : 'false'); });
      if (v === 'map') { resize(); draw(); }
    }
    root.querySelectorAll('[data-u-show]').forEach(function (b) {
      b.addEventListener('click', function () { showView(b.getAttribute('data-u-show')); });
    });
    if (searchIn) {
      var t = 0;
      searchIn.addEventListener('focus', function () { if (D) loadSearch().catch(function () {}); });
      searchIn.addEventListener('input', function () { clearTimeout(t); t = setTimeout(runSearch, 120); });
      searchIn.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          clearTimeout(t);
          runSearch();
          var go = function () { if (matchList.length) select(matchList[0], { trail: true }); };
          if (searchLoading) searchLoading.then(function () { setTimeout(go, 0); }); else go();
        } else if (e.key === 'Escape' && searchIn.value) {
          e.preventDefault(); e.stopPropagation();
          searchIn.value = ''; runSearch();
        }
      });
    }
    document.addEventListener('keydown', function (e) {
      var tag = e.target && e.target.tagName;
      var typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target && e.target.isContentEditable);
      if (e.key === 'Escape') {
        if (document.querySelector('dialog[open]')) return;
        if (sel || !viewFitted) { e.preventDefault(); stepBack(); }
        return;
      }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === '/' && searchIn && !document.querySelector('dialog[open]')) {
        // The site's own search owns '/' elsewhere; on this page it finds on the map.
        e.preventDefault(); e.stopImmediatePropagation(); searchIn.focus(); searchIn.select(); return;
      }
      var held = document.activeElement;
      if (held && held !== document.body && held !== canvas) return;
      var arrow = { ArrowLeft: [1, 0], ArrowRight: [-1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[e.key];
      if (arrow) {
        e.preventDefault();
        var step = e.shiftKey ? 240 : 80;
        cameraTo({ k: view.k, tx: view.tx + arrow[0] * step, ty: view.ty + arrow[1] * step }, false);
      } else if (e.key === '+' || e.key === '=') { e.preventDefault(); root.querySelector('[data-u-zoom="in"]').click(); }
      else if (e.key === '-' || e.key === '_') { e.preventDefault(); root.querySelector('[data-u-zoom="out"]').click(); }
      else if (e.key === '0') { e.preventDefault(); cameraTo(fitView(), true); }
    }, true);
    window.addEventListener('hashchange', function () {
      var key = readHash();
      if (key !== sel) select(key, {});
    });
    function readHash() {
      var hash = window.location.hash || '';
      var m = /^#o=(.+)$/.exec(hash);
      if (m) {
        var key;
        try { key = decodeURIComponent(m[1]); } catch (e) { key = null; }
        if (key && obj(key)) return key;
      }
      return oldHash(hash);
    }
    /* The treemap that stood here before (now tiles.html) kept its place as
       #d=<discipline slug>&f=<family id>&o=<lens>. Such a link opens the same
       family, or the discipline, and the address takes the map's own form. */
    function oldHash(hash) {
      if (!/^#(?:[^=&]+=[^&]*&)*(?:d|f)=/.test(hash)) return null;
      var params = {};
      hash.slice(1).split('&').forEach(function (kv) {
        var i = kv.indexOf('='), k = i < 0 ? kv : kv.slice(0, i), v = i < 0 ? '' : kv.slice(i + 1);
        try { params[k] = decodeURIComponent(v.replace(/\+/g, ' ')); } catch (e) { params[k] = v; }
      });
      var key = params.f && obj('f:' + params.f) ? 'f:' + params.f : params.d && obj('d:' + params.d) ? 'd:' + params.d : null;
      if (key && window.history && window.history.replaceState) {
        window.history.replaceState(null, '', window.location.pathname + window.location.search + '#o=' + encodeURIComponent(key));
      }
      return key;
    }
    function onTheme() { parsedColors = {}; readPalette(); draw(); }
    window.addEventListener('atlas-theme', onTheme);
    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      if (mq.addEventListener) mq.addEventListener('change', onTheme);
    }
    if (window.ResizeObserver) new ResizeObserver(function () { if (resize()) draw(); }).observe(canvas);
    else window.addEventListener('resize', function () { if (resize()) draw(); });

    /* ---- Start ------------------------------------------------------------ */
    readPalette();
    Promise.all([fetchJson(root.getAttribute('data-universe-data')), fetchJson(root.getAttribute('data-universe-layout'))])
      .then(function (both) {
        validate(both[0], both[1]);
        ingest(both[0], both[1]);
        readFonts();
        var ready = Promise.resolve();
        if (document.fonts && document.fonts.load) {
          ready = Promise.all(['400 13px ', '600 13px ', 'italic 400 12px '].map(function (w) {
            return Promise.all([document.fonts.load(w + SERIF), document.fonts.load(w + SANS)]);
          })).then(function () { return document.fonts.ready; });
        }
        return Promise.race([ready, new Promise(function (r) { setTimeout(r, 1500); })]);
      })
      .then(function () {
        widthCache = {};
        W = H = 0;
        resize();
        computeFit();
        if (legendBody && !legendBody.querySelector('.u-key')) legendBody.innerHTML = legendHtml();
        var start = readHash();
        sel = start;
        if (start) {
          var o = obj(start);
          setView(frameFor(o));
          viewFitted = false;
        } else setView(fitView());
        renderPanel();
        if (statusEl) statusEl.hidden = true;
        root.classList.add('is-ready');
        paint();
        window.__universe = {
          select: function (key) { select(key, { trail: true }); },
          state: function () { return { sel: sel, view: viewNow(), fitK: fitK, W: W, H: H, trail: trail.length }; },
          plan: function () { return lastPlan; },
          hover: function (key) { hover = key; paint(); },
          paint: paint,
          fitted: function () { return viewFitted; }
        };
        if (document.fonts && document.fonts.addEventListener) {
          document.fonts.addEventListener('loadingdone', function () { widthCache = {}; computeFit(); if (viewFitted) setView(fitView()); draw(); });
        }
      })
      .catch(function (err) {
        if (statusEl) { statusEl.hidden = false; statusEl.textContent = T('status.load_failed'); }
        root.classList.add('is-failed');
        if (window.console) console.warn('universe:', err && err.message ? err.message : err);
      });
  }

  function boot() {
    var root = document.querySelector('[data-universe]');
    if (root) mount(root);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
