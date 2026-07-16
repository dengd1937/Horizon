"""Shared stylesheet for the static reading site (digest / article / index).

Single source: the acceptance-approved design draft. Inlined into every
generated page so each file is self-contained and offline-readable.
"""

SITE_CSS = """
:root {
  --paper: #FAF9F5; --ink: #21252A; --sub: #6E7379; --line: #E6E3DA;
  --card: #FFFFFF; --card-line: #E1DED4;
  --accent: #17575C; --accent-soft: #17575C14;
  --signal: #DE9526; --signal-soft: #DE952622; --hatch: #F1EFE8;
  --serif: "Songti SC", "Noto Serif SC", Georgia, serif;
  --sans: -apple-system, "PingFang SC", "Helvetica Neue", "Microsoft YaHei", sans-serif;
  --mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #15181B; --ink: #E8E5DE; --sub: #9BA1A8; --line: #2A2F35;
    --card: #1C2025; --card-line: #31373E;
    --accent: #5FBCB0; --accent-soft: #5FBCB01F;
    --signal: #E8A33D; --signal-soft: #E8A33D26; --hatch: #21262B;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  * { animation: none !important; transition: none !important; }
}
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: var(--sans); font-size: 16px; line-height: 1.78;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; text-underline-offset: 3px; }
a:focus-visible, summary:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 3px;
}
.wrap { max-width: 720px; margin: 0 auto; padding: 0 20px 80px; }

.mast { padding-top: 34px; }
.mast-top {
  display: flex; justify-content: space-between; align-items: baseline;
  font-family: var(--mono); font-size: 12px; letter-spacing: .14em; color: var(--sub);
}
.mast-top .brand { color: var(--ink); font-weight: 700; }
.mast-links { display: flex; gap: 16px; }
.mast h1 {
  font-family: var(--serif); font-weight: 700; font-size: 46px;
  margin: 18px 0 4px; letter-spacing: .01em;
}
.mast h1 small {
  font-family: var(--mono); font-size: 13px; font-weight: 400;
  color: var(--sub); letter-spacing: .12em; margin-left: 14px;
}
.mast .stats { font-family: var(--mono); font-size: 12.5px; color: var(--sub); margin: 2px 0 0; }
.mast .stats b { color: var(--signal); font-weight: 600; }

.band { display: flex; align-items: flex-end; gap: 7px; height: 52px; margin: 26px 0 8px; }
.band a {
  display: block; width: 16px; border-radius: 3px 3px 0 0;
  background: var(--signal); transition: opacity .15s, transform .15s;
}
.band a:hover { opacity: 1 !important; transform: scaleY(1.06); transform-origin: bottom; }
.band-hint { font-family: var(--mono); font-size: 11.5px; color: var(--sub); margin: 0 0 26px; }
hr.rule { border: 0; border-top: 1px solid var(--line); margin: 0; }

.toc { margin: 30px 0 10px; padding: 0; list-style: none; counter-reset: n; }
.toc li {
  counter-increment: n; display: flex; align-items: baseline; gap: 12px;
  padding: 7px 0; border-bottom: 1px dashed var(--line);
}
.toc li::before {
  content: counter(n, decimal-leading-zero);
  font-family: var(--mono); font-size: 12px; color: var(--sub);
}
.toc a { color: var(--ink); flex: 1; }
.toc a:hover { color: var(--accent); }
.toc .s { font-family: var(--mono); font-size: 12.5px; color: var(--signal); }

.item { padding: 44px 0 36px; border-bottom: 1px solid var(--line); position: relative; }
.item:last-of-type { border-bottom: 0; }
.item:target::before {
  content: ""; position: absolute; left: -20px; top: 44px; bottom: 36px; width: 3px;
  background: var(--signal); border-radius: 2px; animation: settle 2.4s ease-out;
}
@keyframes settle { 0% { opacity: 1; } 70% { opacity: 1; } 100% { opacity: .45; } }
.item-head { display: flex; align-items: baseline; gap: 12px; }
.item-head .no { font-family: var(--mono); font-size: 12.5px; color: var(--sub); }
.item-head .score {
  font-family: var(--mono); font-size: 13px; font-weight: 600; color: var(--signal);
  background: var(--signal-soft); padding: 1px 8px; border-radius: 4px;
}
.item h2 { font-family: var(--serif); font-size: 23px; line-height: 1.45; margin: 10px 0 14px; font-weight: 700; }
.item .summary { margin: 0 0 18px; }
.meta {
  font-family: var(--mono); font-size: 12px; color: var(--sub);
  margin-top: 16px; display: flex; flex-wrap: wrap; gap: 6px 14px;
}
.meta a { color: var(--sub); border-bottom: 1px dotted var(--sub); }
.meta a:hover { color: var(--accent); text-decoration: none; }

details { border: 1px solid var(--line); border-radius: 10px; margin-top: 10px; }
details summary {
  cursor: pointer; list-style: none; padding: 9px 14px;
  font-size: 13.5px; color: var(--sub); user-select: none;
}
details summary::-webkit-details-marker { display: none; }
details summary::before { content: "\\25B8"; display: inline-block; margin-right: 8px; transition: transform .15s; }
details[open] summary::before { transform: rotate(90deg); }
details[open] summary { color: var(--ink); border-bottom: 1px dashed var(--line); }
details .fold-body { padding: 12px 16px 14px; font-size: 14.5px; color: var(--sub); }

details.tweet-fold { border: 0; border-radius: 0; margin-top: 0; }
details.tweet-fold > summary {
  padding: 0; color: inherit; border: 0; border-radius: 14px;
}
details.tweet-fold > summary::before { display: none; }
details.tweet-fold[open] > summary { border: 0; color: inherit; }
.tweet-preview {
  display: block; background: var(--card); border: 1px solid var(--card-line);
  border-radius: 14px; padding: 15px 18px 12px;
}
.tweet-preview-content { display: block; }
.tweet-preview-head {
  display: flex; align-items: baseline; flex-wrap: wrap; gap: 5px 10px;
  font-size: 13.5px; color: var(--sub); margin-bottom: 7px;
}
.tweet-preview-head b { color: var(--ink); font-size: 14.5px; font-weight: 600; }
.tweet-preview-facts {
  margin-left: auto; font-family: var(--mono); font-size: 11.5px;
  color: var(--signal);
}
.tweet-preview-text {
  display: -webkit-box; overflow: hidden; overflow-wrap: break-word;
  -webkit-box-orient: vertical; -webkit-line-clamp: 4;
  white-space: pre-line; font-size: 15px; line-height: 1.7; color: var(--ink);
}
.tweet-preview-media {
  display: block; position: relative; margin-top: 12px; overflow: hidden;
  border: 1px solid var(--card-line); border-radius: 10px; background: var(--hatch);
}
.tweet-preview-media img {
  width: 100%; max-height: 320px; display: block; object-fit: cover;
}
.media-play {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
  width: 48px; height: 48px; display: grid; place-items: center;
  border-radius: 50%; color: #fff; background: #111A; border: 1px solid #FFF8;
  padding-left: 3px; font-size: 18px;
}
.media-more {
  position: absolute; right: 10px; top: 10px; padding: 2px 8px;
  border-radius: 5px; background: #111C; color: #fff;
  font-family: var(--mono); font-size: 11.5px;
}
.tweet-preview-media.media-placeholder { min-height: 170px; }
.media-placeholder-label {
  position: absolute; left: 50%; top: calc(50% + 38px); transform: translateX(-50%);
  color: var(--sub); font-family: var(--mono); font-size: 12px;
}
.tweet-fold-action {
  display: block; margin-top: 10px; color: var(--accent);
  font-size: 13px; font-weight: 500;
}
.tweet-fold-action::before {
  content: "\\25B8"; display: inline-block; margin-right: 7px;
  transition: transform .15s;
}
.tweet-fold[open] .tweet-fold-action::before { transform: rotate(90deg); }
.tweet-fold .when-open { display: none; }
.tweet-fold[open] .when-closed { display: none; }
.tweet-fold[open] .when-open { display: inline; }
.tweet-fold[open] .tweet-preview-content { display: none; }
.tweet-fold[open] .tweet-preview { padding-bottom: 10px; }
.tweet-fold[open] .tweet-fold-action { margin-top: 0; }
.tweet-fold-body { padding-top: 10px; }

.tweet {
  background: var(--card); border: 1px solid var(--card-line); border-radius: 14px;
  padding: 16px 18px; font-size: 15px; line-height: 1.7;
}
.rt-line { font-size: 13px; color: var(--sub); margin: 0 0 10px; }
.rt-line svg { vertical-align: -2px; margin-right: 5px; }
.t-author { font-size: 14.5px; margin: 0 0 6px; }
.t-author b { font-weight: 600; }
.t-author .h { color: var(--sub); font-weight: 400; margin-left: 5px; }
.t-text { margin: 0; white-space: pre-line; overflow-wrap: break-word; }
.tweet .tweet { margin-top: 12px; border-radius: 12px; padding: 12px 14px; font-size: 14px; background: var(--paper); }

.thread { display: grid; grid-template-columns: 18px 1fr; column-gap: 12px; margin-top: 12px; }
.thread .tick { position: relative; }
.thread .tick::before {
  content: ""; position: absolute; left: 50%; top: 7px; width: 9px; height: 9px;
  margin-left: -5px; border-radius: 50%; background: var(--card-line);
}
.thread .tick::after {
  content: ""; position: absolute; left: 50%; top: 20px; bottom: -6px; width: 2px;
  margin-left: -1px; background: var(--line);
}
.thread .tick.last::after { display: none; }
.thread .seg { padding-bottom: 18px; min-width: 0; }
.thread .seg:last-of-type { padding-bottom: 0; }
.thread .seg p { margin: 0; }

.media { margin-top: 12px; }
.media img, .media video {
  width: 100%; display: block; border-radius: 10px;
  border: 1px solid var(--card-line); height: auto;
}
.media video { background: #000; }
.media.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.gifwrap { position: relative; }
.gifwrap .tag {
  position: absolute; left: 10px; bottom: 10px; background: var(--card);
  border: 1px solid var(--card-line); border-radius: 5px; padding: 1px 8px;
  font-size: 11px; color: var(--sub);
}

.linkcard {
  display: flex; margin-top: 12px; border: 1px solid var(--card-line);
  border-radius: 10px; overflow: hidden; color: inherit;
}
.linkcard:hover { text-decoration: none; border-color: var(--accent); }
.linkcard .thumb {
  width: 88px; min-height: 68px; flex-shrink: 0;
  border-right: 1px solid var(--card-line); background: var(--hatch);
  object-fit: cover;
}
.linkcard .lc-body { padding: 10px 14px; min-width: 0; }
.linkcard .lc-title { font-size: 14px; font-weight: 600; line-height: 1.45; margin: 0; }
.linkcard .lc-domain { font-family: var(--mono); font-size: 11.5px; color: var(--sub); margin: 4px 0 0; }

.articlecard {
  display: block; margin-top: 12px; border: 1px solid var(--card-line);
  border-radius: 12px; overflow: hidden; color: inherit;
}
.articlecard:hover { text-decoration: none; border-color: var(--accent); }
.articlecard .cover {
  width: 100%; aspect-ratio: 21 / 8; object-fit: cover; display: block;
  border-bottom: 1px solid var(--card-line); background: var(--hatch);
}
.articlecard .ac-body { padding: 14px 18px 16px; }
.articlecard .ac-kicker {
  font-family: var(--mono); font-size: 11px; letter-spacing: .12em;
  color: var(--signal); margin: 0 0 6px;
}
.articlecard .ac-title { font-family: var(--serif); font-size: 18px; font-weight: 700; margin: 0 0 6px; line-height: 1.5; }
.articlecard .ac-preview { font-size: 13.5px; color: var(--sub); margin: 0 0 10px; }
.articlecard .ac-cta { font-size: 13.5px; color: var(--accent); font-weight: 500; }

.foot {
  margin-top: 46px; font-family: var(--mono); font-size: 12px; color: var(--sub);
  display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;
}

.art-top {
  padding: 26px 0 0; display: flex; justify-content: space-between;
  font-family: var(--mono); font-size: 12px; letter-spacing: .14em; color: var(--sub);
}
.art-top .brand { color: var(--ink); font-weight: 700; }
.art-kicker { font-family: var(--mono); font-size: 11.5px; letter-spacing: .14em; color: var(--signal); margin: 44px 0 10px; }
.art-title { font-family: var(--serif); font-size: 32px; line-height: 1.5; margin: 0 0 14px; font-weight: 700; }
.art-byline {
  font-family: var(--mono); font-size: 12.5px; color: var(--sub);
  margin: 0 0 30px; display: flex; flex-wrap: wrap; gap: 6px 14px;
}
.art-byline a { color: var(--sub); border-bottom: 1px dotted var(--sub); }
.art-cover { width: 100%; max-width: 100%; border: 1px solid var(--card-line); border-radius: 12px; display: block; margin: 0 0 38px; height: auto; }
.prose { font-size: 17px; line-height: 1.9; }
.prose p { margin: 0 0 1.35em; }
.prose h2, .prose h3, .prose h4 { font-family: var(--serif); line-height: 1.5; margin: 1.6em 0 .6em; }
.prose figure { margin: 1.6em 0; }
.prose img, .prose video {
  width: 100%; max-width: 100%; height: auto; display: block;
  border: 1px solid var(--card-line); border-radius: 10px;
}
.prose video { background: #000; }
.prose blockquote {
  border-left: 3px solid var(--card-line); margin: 1.4em 0; padding: 2px 0 2px 16px;
  color: var(--sub);
}
.prose pre {
  background: var(--card); border: 1px solid var(--card-line); border-radius: 10px;
  padding: 14px 16px; overflow-x: auto; font-size: 13.5px;
}
.prose code { font-family: var(--mono); }
.backline { margin-top: 34px; font-size: 14.5px; }

.idx-title { font-family: var(--serif); font-size: 40px; margin: 16px 0 6px; }
.idx-sub { font-family: var(--mono); font-size: 12.5px; color: var(--sub); margin: 0 0 40px; }
.idx-month { font-family: var(--mono); font-size: 12px; font-weight: 400; letter-spacing: .16em; color: var(--sub); margin: 36px 0 8px; }
.day { display: flex; align-items: baseline; gap: 14px; padding: 12px 2px; border-bottom: 1px dashed var(--line); color: inherit; }
.day:hover { border-bottom-color: var(--accent); text-decoration: none; }
.day .d { font-family: var(--serif); font-size: 18px; font-weight: 700; min-width: 88px; }
.day .n { font-family: var(--mono); font-size: 12.5px; color: var(--signal); }
.day .t {
  flex: 1; color: var(--sub); font-size: 14px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.art-source { font-size: 15.5px; margin: 0 0 6px; }
.art-source a { font-weight: 600; }
.art-license { font-family: var(--mono); font-size: 11.5px; color: var(--sub); margin: 0 0 30px; }
.intro { border-left: 3px solid var(--accent); margin: 0 0 30px; padding: 4px 0 4px 16px; color: var(--sub); font-size: 15.5px; }
.intro p { margin: 0; }
.pagenav {
  margin-top: 50px; padding-top: 22px; border-top: 1px solid var(--line);
  display: flex; justify-content: space-between; align-items: flex-start; gap: 14px;
}
.pagenav .prev, .pagenav .next { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.pagenav .next { text-align: right; align-items: flex-end; }
.pagenav .up { font-family: var(--mono); font-size: 12px; color: var(--sub); flex-shrink: 0; }
.pagenav .muted { flex: 1; }
.pagenav .dir { font-family: var(--mono); font-size: 11px; color: var(--sub); letter-spacing: .1em; }
.pagenav .ttl { font-family: var(--serif); font-size: 14.5px; color: var(--ink); }
.art-entry { display: block; padding: 16px 2px; border-bottom: 1px dashed var(--line); color: inherit; }
.art-entry:hover { border-bottom-color: var(--accent); text-decoration: none; }
.art-entry .day-tag { font-family: var(--mono); font-size: 11.5px; color: var(--signal); letter-spacing: .1em; display: block; margin-bottom: 5px; }
.art-entry .ttl { font-family: var(--serif); font-size: 18px; font-weight: 700; display: block; margin-bottom: 5px; }
.art-entry .meta { font-family: var(--mono); font-size: 11.5px; color: var(--sub); display: block; margin-bottom: 5px; }
.art-entry .sum { font-size: 13.5px; color: var(--sub); display: block; }
.empty { color: var(--sub); font-family: var(--mono); font-size: 13px; padding: 40px 0; }

@media (max-width: 560px) {
  body { font-size: 15.5px; }
  .mast h1 { font-size: 36px; }
  .item h2 { font-size: 20px; }
  .tweet { padding: 13px 14px; }
  .tweet-preview { padding: 13px 14px 11px; }
  .tweet-preview-facts { width: 100%; margin-left: 0; }
  .tweet-preview-media img { max-height: 230px; }
  .tweet-preview-media.media-placeholder { min-height: 140px; }
  .media-play { width: 42px; height: 42px; }
  .media.grid { grid-template-columns: 1fr; }
  .item:target::before { left: -12px; }
  .art-title { font-size: 26px; }
  .prose { font-size: 16px; }
  .idx-title { font-size: 32px; }
  .day .t { display: none; }
}
"""
