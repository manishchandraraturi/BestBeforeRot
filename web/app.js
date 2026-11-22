/* BestBeforeRot — console behaviour (P7b) + results polish (P7c)
   Talks only to POST /api/verify (02-ARCHITECTURE.md §5). */

(function () {
  "use strict";

  var CIRC = 2 * Math.PI * 70; // score ring radius 70
  var TTL_CIRC = 2 * Math.PI * 14; // TTL ring radius 14
  var TICKER = [
    "SPLITTING CLAIMS",
    "CHECKING THE LIVE WEB",
    "JUDGING EVIDENCE",
    "WRITING FIXES",
  ];

  var SAMPLES = {
    pricing:
      "The Notion Plus plan costs $5 per month. Sam Altman is the CEO of OpenAI. The Eiffel Tower is in Paris.",
    version:
      "Python 3.11 is the latest stable release of Python. It ships the faster CPython interpreter and is recommended for new projects.",
    ceo:
      "Sam Altman is the CEO of OpenAI. Notion Plus costs $5 per month. The Eiffel Tower is in Paris.",
  };

  var answer = document.getElementById("answer");
  var verifyBtn = document.getElementById("verify");
  var retryBtn = document.getElementById("retry");
  var useCache = document.getElementById("use-cache");
  var forceFallback = document.getElementById("force-fallback");
  var result = document.getElementById("result");
  var resultMeta = document.getElementById("result-meta");
  var ticker = document.getElementById("ticker");
  var score = document.getElementById("score");
  var scoreValue = document.getElementById("score-value");
  var scoreBand = document.getElementById("score-band");
  var scoreRing = document.getElementById("score-ring");
  var statsEl = document.getElementById("stats");
  var badgesEl = document.getElementById("badges");
  var claimsEl = document.getElementById("claims");
  var errorMsg = document.getElementById("error-msg");
  var tabsEl = document.querySelector(".tabs");
  var tabButtons = Array.prototype.slice.call(document.querySelectorAll(".tab"));
  var copyBtn = document.getElementById("copy");
  var answerText = document.getElementById("answer-text");

  var tickerTimer = null;
  var countFrame = null;
  var copyTimer = null;
  var lastResult = null;
  var activeTab = "corrected";

  /* ── states ─────────────────────────────────────────────── */

  function setState(state, meta) {
    result.setAttribute("data-state", state);
    if (meta) resultMeta.textContent = meta;
  }

  function startTicker() {
    var i = 0;
    ticker.textContent = TICKER[0];
    clearInterval(tickerTimer);
    tickerTimer = setInterval(function () {
      i = (i + 1) % TICKER.length;
      ticker.textContent = TICKER[i];
    }, 1100);
  }

  function stopTicker() {
    clearInterval(tickerTimer);
    tickerTimer = null;
  }

  function setBusy(busy) {
    verifyBtn.classList.toggle("is-loading", busy);
    verifyBtn.disabled = busy;
    answer.readOnly = busy;
  }

  function showError(message) {
    stopTicker();
    errorMsg.textContent = message;
    setState("error", "FAILED");
  }

  function svg(tag, attrs) {
    var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.keys(attrs).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    return node;
  }

  /* ── score ring ─────────────────────────────────────────── */

  function countUp(el, target, duration) {
    var from = Number(el.getAttribute("data-value") || 0);
    var start = null;
    var settled = false;

    if (countFrame) cancelAnimationFrame(countFrame);
    el.setAttribute("data-value", String(target));

    function finish() {
      if (settled) return;
      settled = true;
      countFrame = null;
      el.textContent = String(target);
    }

    function step(now) {
      if (settled) return;
      if (start === null) start = now;
      var t = Math.min(1, (now - start) / duration);
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = String(Math.round(from + (target - from) * eased));
      if (t < 1) countFrame = requestAnimationFrame(step);
      else finish();
    }

    countFrame = requestAnimationFrame(step);
    // rAF pauses in a hidden/minimised window; snap to the final number anyway.
    setTimeout(finish, duration + 150);
  }

  function paintScore(value, band) {
    var safe = Math.max(0, Math.min(100, Number(value) || 0));
    score.setAttribute("data-band", band || "mixed");
    scoreBand.textContent = band || "—";

    var target = CIRC * (1 - safe / 100);
    scoreRing.style.strokeDashoffset = String(CIRC);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        scoreRing.style.strokeDashoffset = String(target);
      });
    });
    // Same guard as the count-up: no frames in a hidden window.
    setTimeout(function () {
      scoreRing.style.strokeDashoffset = String(target);
    }, 1350);
    countUp(scoreValue, safe, 1200);
  }

  /* ── result rendering ───────────────────────────────────── */

  function cell(label, value) {
    var span = document.createElement("span");
    var b = document.createElement("b");
    b.textContent = String(value);
    span.appendChild(document.createTextNode(label + " "));
    span.appendChild(b);
    return span;
  }

  function paintStats(stats) {
    stats = stats || {};
    statsEl.textContent = "";
    var cells = [
      cell("CLAIMS", stats.claims_total || 0),
      cell("SEARCHED", stats.claims_searched || 0),
      cell("SKIPPED", stats.claims_skipped_stable || 0),
      cell("CACHE", stats.cache_hits || 0),
      cell("LATENCY", ((stats.latency_ms || 0) / 1000).toFixed(1) + "s"),
    ];
    cells.forEach(function (node, index) {
      if (index) {
        var sep = document.createElement("span");
        sep.className = "stats-sep";
        sep.setAttribute("aria-hidden", "true");
        sep.textContent = "·";
        statsEl.appendChild(sep);
      }
      statsEl.appendChild(node);
    });
  }

  function badge(text, extraClass) {
    var span = document.createElement("span");
    span.className = "badge" + (extraClass ? " " + extraClass : "");
    var b = document.createElement("b");
    b.textContent = text;
    span.appendChild(b);
    return span;
  }

  function paintBadges(stats) {
    stats = stats || {};
    var providers = stats.providers_used || [];
    var provider = providers.length ? providers[providers.length - 1] : "unknown";
    badgesEl.textContent = "";

    if (stats.fallback_triggered) {
      var fallback = badge("FALLBACK → " + provider, "is-fallback");
      fallback.setAttribute("title", "The primary model failed; Bifrost rerouted");
      badgesEl.appendChild(fallback);
    } else {
      badgesEl.appendChild(badge("ROUTED VIA " + provider));
    }

    if (stats.cache_hits > 0) {
      badgesEl.appendChild(badge("FROM CACHE", "is-cache"));
    }
  }

  function hostOf(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch (err) {
      return url;
    }
  }

  function dotClass(claim) {
    if (claim.status === "skipped_stable") return "is-none";
    if (claim.verdict === "fresh") return "is-fresh";
    if (claim.verdict === "stale") return "is-stale";
    return "is-unsure";
  }

  function verdictWord(claim) {
    if (claim.status === "skipped_stable") return "SKIPPED";
    if (claim.verdict) return String(claim.verdict).toUpperCase();
    return "CHECKED";
  }

  /* ── TTL ring ───────────────────────────────────────────── */

  function ttlFraction(claim) {
    if (!claim.ttl_days || !claim.expires_at) return 1;
    var total = claim.ttl_days * 86400000;
    var left = new Date(claim.expires_at).getTime() - Date.now();
    if (!isFinite(left)) return 1;
    return Math.max(0, Math.min(1, left / total));
  }

  function ttlLabel(claim) {
    if (!claim.ttl_days) return "∞";
    return claim.ttl_days + "d";
  }

  function ttlRing(claim) {
    var wrap = document.createElement("div");
    wrap.className = "ttl";
    wrap.setAttribute("title", "Expires in " + ttlLabel(claim) + " (TTL)");

    var ring = svg("svg", { viewBox: "0 0 36 36", "aria-hidden": "true" });
    ring.appendChild(
      svg("circle", { class: "ttl-track", cx: 18, cy: 18, r: 14 })
    );
    var progress = svg("circle", {
      class: "ttl-progress",
      cx: 18,
      cy: 18,
      r: 14,
    });
    progress.style.strokeDashoffset = String(
      TTL_CIRC * (1 - ttlFraction(claim))
    );
    ring.appendChild(progress);

    var label = document.createElement("span");
    label.className = "ttl-label";
    label.textContent = ttlLabel(claim);

    wrap.appendChild(ring);
    wrap.appendChild(label);
    return wrap;
  }

  /* ── claim card ─────────────────────────────────────────── */

  function claimText(claim) {
    var p = document.createElement("p");
    p.className = "claim-text";
    var stale = claim.verdict === "stale" && !!claim.corrected_text;
    if (stale) p.classList.add("is-stale");

    var words = String(claim.text || "").split(/\s+/).filter(Boolean);
    words.forEach(function (word, index) {
      if (stale) {
        var span = document.createElement("span");
        span.className = "strike-word";
        span.style.setProperty("--i", index);
        span.textContent = word;
        p.appendChild(span);
      } else {
        p.appendChild(document.createTextNode(word));
      }
      if (index < words.length - 1) p.appendChild(document.createTextNode(" "));
    });

    return p;
  }

  function claimCard(claim, index) {
    var card = document.createElement("article");
    card.className = "claim";
    card.style.setProperty("--ci", index || 0);
    card.setAttribute("data-verdict", claim.verdict || claim.status || "unverifiable");

    var head = document.createElement("div");
    head.className = "claim-head";

    var dot = document.createElement("span");
    dot.className = "dot " + dotClass(claim);
    dot.setAttribute("aria-hidden", "true");
    head.appendChild(dot);

    var typeTag = document.createElement("span");
    typeTag.className = "tag";
    typeTag.textContent = String(claim.type || "other").toUpperCase();
    head.appendChild(typeTag);

    var word = document.createElement("span");
    word.className = "claim-verdict";
    word.textContent = verdictWord(claim);
    head.appendChild(word);

    head.appendChild(ttlRing(claim));
    card.appendChild(head);

    card.appendChild(claimText(claim));

    if (claim.corrected_text && claim.verdict === "stale") {
      var fix = document.createElement("p");
      fix.className = "claim-fix";
      fix.textContent = claim.corrected_text;
      // Let the word-by-word strike finish before the fix fades in.
      fix.style.animationDelay =
        Math.min(1.2, 0.25 + words(claim.text).length * 0.045) + "s";
      card.appendChild(fix);
    }

    var sources = claim.sources || [];
    if (sources.length) {
      var row = document.createElement("div");
      row.className = "sources";
      sources.forEach(function (source) {
        if (!source || !source.url) return;
        var link = document.createElement("a");
        link.className = "source";
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = hostOf(source.url) + " ↗";
        if (source.title) link.title = source.title;
        row.appendChild(link);
      });
      if (row.childNodes.length) card.appendChild(row);
    }

    return card;
  }

  function paintClaims(claims) {
    claimsEl.textContent = "";
    if (!claims || !claims.length) {
      var empty = document.createElement("p");
      empty.className = "claim-empty";
      empty.textContent = "Nothing here can go stale ✦ all claims are stable.";
      claimsEl.appendChild(empty);
      return;
    }
    claims.forEach(function (claim, index) {
      claimsEl.appendChild(claimCard(claim, index));
    });
  }

  /* ── answer tabs + diff ─────────────────────────────────── */

  function words(text) {
    return String(text || "").split(/\s+/).filter(Boolean);
  }

  /* Word-level LCS diff: returns [{ t: "same" | "del" | "ins", w }]. */
  function diffWords(before, after) {
    var a = words(before);
    var b = words(after);
    var n = a.length;
    var m = b.length;
    var table = [];
    var i;
    var j;

    for (i = 0; i <= n; i++) {
      table.push(new Array(m + 1).fill(0));
    }
    for (i = n - 1; i >= 0; i--) {
      for (j = m - 1; j >= 0; j--) {
        table[i][j] =
          a[i] === b[j]
            ? table[i + 1][j + 1] + 1
            : Math.max(table[i + 1][j], table[i][j + 1]);
      }
    }

    var ops = [];
    i = 0;
    j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) {
        ops.push({ t: "same", w: a[i] });
        i++;
        j++;
      } else if (table[i + 1][j] >= table[i][j + 1]) {
        ops.push({ t: "del", w: a[i] });
        i++;
      } else {
        ops.push({ t: "ins", w: b[j] });
        j++;
      }
    }
    while (i < n) ops.push({ t: "del", w: a[i++] });
    while (j < m) ops.push({ t: "ins", w: b[j++] });
    return ops;
  }

  function paintAnswer(tab) {
    activeTab = tab || "corrected";
    tabButtons.forEach(function (button) {
      var on = button.getAttribute("data-tab") === activeTab;
      button.classList.toggle("is-active", on);
      button.setAttribute("aria-selected", on ? "true" : "false");
    });

    answerText.textContent = "";
    if (!lastResult) return;

    if (activeTab === "diff") {
      diffWords(lastResult.original_answer, lastResult.corrected_answer).forEach(
        function (op, index, all) {
          var node;
          if (op.t === "same") {
            node = document.createTextNode(op.w);
          } else {
            node = document.createElement(op.t === "del" ? "s" : "u");
            node.textContent = op.w;
          }
          answerText.appendChild(node);
          if (index < all.length - 1) {
            answerText.appendChild(document.createTextNode(" "));
          }
        }
      );
      return;
    }

    answerText.textContent =
      activeTab === "original"
        ? lastResult.original_answer
        : lastResult.corrected_answer;
  }

  function setCopyLabel(text, copied) {
    copyBtn.textContent = text;
    copyBtn.classList.toggle("is-copied", !!copied);
  }

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
    } catch (err) {
      /* nothing else we can do; the label still confirms the attempt */
    }
    document.body.removeChild(ta);
  }

  function copyCorrected() {
    if (!lastResult) return;
    var text = lastResult.corrected_answer || lastResult.original_answer || "";

    var done = function () {
      setCopyLabel("Copied!", true);
      clearTimeout(copyTimer);
      copyTimer = setTimeout(function () {
        setCopyLabel("Copy corrected", false);
      }, 2000);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () {
        fallbackCopy(text);
        done();
      });
    } else {
      fallbackCopy(text);
      done();
    }
  }

  function render(data) {
    stopTicker();
    lastResult = data;
    setState("result", "CHECKED");
    paintScore(data.overall_score, data.overall_band);
    paintStats(data.stats);
    paintBadges(data.stats);
    paintClaims(data.claims);
    paintAnswer("corrected");
    setCopyLabel("Copy corrected", false);
  }

  /* ── request ────────────────────────────────────────────── */

  function failureMessage(status, body) {
    if (body && body.error) {
      if (status === 503) {
        return (
          body.error +
          " — start it with “npx -y @maximhq/bifrost” and try again."
        );
      }
      return body.error;
    }
    if (status === 503) {
      return "The Bifrost gateway is offline. Start it with “npx -y @maximhq/bifrost” and try again.";
    }
    if (status === 502) {
      return "An upstream service failed before the check finished (HTTP 502). Try again.";
    }
    return "The check failed (HTTP " + status + "). Try again.";
  }

  function verify() {
    var text = answer.value.trim();

    if (text.length < 20) {
      showError(
        "Give me at least 20 characters of AI answer — a sentence or three works best."
      );
      answer.focus();
      return;
    }

    setBusy(true);
    errorMsg.textContent = "";
    setState("loading", "CHECKING");
    startTicker();

    fetch("/api/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        answer: text,
        force_fallback: forceFallback.checked,
        use_cache: useCache.checked,
      }),
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return null;
          })
          .then(function (body) {
            return { response: response, body: body };
          });
      })
      .then(function (res) {
        if (!res.response.ok) {
          showError(failureMessage(res.response.status, res.body));
          return;
        }
        if (!res.body || typeof res.body.overall_score !== "number") {
          showError("The checker returned an unexpected response. Try again.");
          return;
        }
        render(res.body);
      })
      .catch(function () {
        showError(
          "Could not reach the checker. Make sure the app is running on 127.0.0.1:8000."
        );
      })
      .finally(function () {
        setBusy(false);
      });
  }

  /* ── wiring ─────────────────────────────────────────────── */

  verifyBtn.addEventListener("click", verify);
  retryBtn.addEventListener("click", verify);

  document.querySelectorAll(".chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var sample = SAMPLES[chip.getAttribute("data-sample")];
      if (!sample) return;
      answer.value = sample;
      answer.focus();
    });
  });

  if (tabsEl) {
    tabsEl.addEventListener("click", function (event) {
      var button = event.target.closest(".tab");
      if (!button) return;
      paintAnswer(button.getAttribute("data-tab"));
    });
  }

  copyBtn.addEventListener("click", copyCorrected);

  /* ── scroll reveal ──────────────────────────────────────── */

  (function reveal() {
    var elements = Array.prototype.slice.call(
      document.querySelectorAll(".reveal")
    );

    function revealInView() {
      elements.forEach(function (el) {
        if (el.classList.contains("in")) return;
        var rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight * 0.95) el.classList.add("in");
      });
    }

    if (!("IntersectionObserver" in window)) {
      elements.forEach(function (el) {
        el.classList.add("in");
      });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("in");
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -8% 0px" }
    );

    elements.forEach(function (el) {
      observer.observe(el);
    });

    // Margin of safety: the observer needs frames, so also check on scroll/load.
    window.addEventListener("scroll", revealInView, { passive: true });
    window.addEventListener("resize", revealInView);
    revealInView();
    setTimeout(revealInView, 1200);
  })();
})();
