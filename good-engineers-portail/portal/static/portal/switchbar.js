/*
 * Barre de bascule GOOD ENGINEERS.
 *
 * À inclure dans les DEUX applications (Forage et Mine). Elle affiche en
 * haut de page les modules de l'entreprise et un lien « Rapport », et
 * permet de passer d'un module à l'autre SANS reconnexion : chaque lien
 * pointe vers le portail (/go/<module>/), qui remet un jeton SSO et
 * redirige vers l'application cible.
 *
 * L'application doit définir, AVANT de charger ce script, un objet de
 * configuration (les valeurs viennent du jeton SSO reçu à la connexion) :
 *
 *   <script>
 *     window.GE_SWITCHBAR = {
 *       portal:     "https://geportail.duckdns.org",
 *       current:    "forage",            // module courant : "forage" | "mine"
 *       modules:    ["forage","mine"],   // modules actifs de l'entreprise
 *       enterprise: "SAHARA MINING"      // nom affiché (facultatif)
 *     };
 *   </script>
 *   <script src="https://geportail.duckdns.org/static/portal/switchbar.js"></script>
 *
 * Si window.GE_SWITCHBAR est absent, la barre ne s'affiche pas (l'app reste
 * utilisable seule, via son ancienne page de connexion).
 */
(function () {
  var cfg = window.GE_SWITCHBAR;
  if (!cfg || !cfg.portal || !Array.isArray(cfg.modules) || cfg.modules.length === 0) return;

  var LABELS = { forage: "Forage", mine: "Mine" };
  var portal = String(cfg.portal).replace(/\/+$/, "");

  var css = ''
    + '.ge-sb{position:sticky;top:0;z-index:99999;display:flex;align-items:center;gap:6px;'
    + 'padding:6px 12px;background:#12151c;border-bottom:1px solid #262b36;'
    + 'font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;font-size:13px;color:#e7e9ee}'
    + '.ge-sb .ge-brand{font-weight:600;margin-right:6px;white-space:nowrap}'
    + '.ge-sb .ge-ent{color:#9aa3b2;margin-right:10px;white-space:nowrap}'
    + '.ge-sb a{display:inline-block;padding:5px 12px;border-radius:7px;text-decoration:none;'
    + 'color:#e7e9ee;border:1px solid #262b36}'
    + '.ge-sb a:hover{border-color:#3a4150}'
    + '.ge-sb a.ge-cur{background:#d8812f;border-color:#d8812f;color:#1a1205;font-weight:600}'
    + '.ge-sb .ge-spacer{flex:1}'
    + '.ge-sb a.ge-rap{color:#9aa3b2}';

  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  var bar = document.createElement("div");
  bar.className = "ge-sb";

  var html = '<span class="ge-brand">GOOD ENGINEERS</span>';
  if (cfg.enterprise) html += '<span class="ge-ent">' + escapeHtml(cfg.enterprise) + '</span>';

  cfg.modules.forEach(function (m) {
    var label = LABELS[m] || m;
    if (m === cfg.current) {
      html += '<a class="ge-cur" aria-current="page">' + escapeHtml(label) + '</a>';
    } else {
      html += '<a href="' + portal + '/go/' + encodeURIComponent(m) + '/">' + escapeHtml(label) + '</a>';
    }
  });

  html += '<span class="ge-spacer"></span>';
  html += '<a class="ge-rap" href="' + portal + '/rapport/">Rapport consolidé</a>';
  html += '<a class="ge-rap" href="' + portal + '/">Portail</a>';

  bar.innerHTML = html;

  if (document.body) document.body.insertBefore(bar, document.body.firstChild);
  else document.addEventListener("DOMContentLoaded", function () {
    document.body.insertBefore(bar, document.body.firstChild);
  });

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
})();
