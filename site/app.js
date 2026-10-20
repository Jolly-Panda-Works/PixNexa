// Point the download buttons straight at the newest files on GitHub Releases.
// Without JavaScript (or if the API is unreachable) the buttons still open the Releases page.
(function () {
  "use strict";
  var REPO = "Usef-Farahmand/image-format-converter";
  var toFa = function (s) { return String(s).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }); };
  var mb = function (bytes) { return toFa((bytes / 1048576).toFixed(1)).replace(".", "٫") + " مگابایت"; };

  function setAll(selector, fn) {
    Array.prototype.forEach.call(document.querySelectorAll(selector), fn);
  }

  function findAsset(release, test) {
    for (var i = 0; i < release.assets.length; i++) if (test(release.assets[i].name)) return release.assets[i];
    return null;
  }

  fetch("https://api.github.com/repos/" + REPO + "/releases?per_page=50", { headers: { Accept: "application/vnd.github+json" } })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (releases) {
      releases = releases.filter(function (r) { return !r.draft; });

      // PixNexa Mobile: tags android-v1.0.N
      for (var i = 0; i < releases.length; i++) {
        var rel = releases[i];
        if (rel.tag_name.indexOf("android-v") !== 0) continue;
        var apk = findAsset(rel, function (n) { return n === "PixNexa.apk"; }) ||
                  findAsset(rel, function (n) { return /\.apk$/i.test(n); });
        if (!apk) continue;
        var version = rel.tag_name.replace("android-v", "");
        setAll('[data-dl="android"]', function (a) { a.href = apk.browser_download_url; a.setAttribute("download", ""); });
        setAll('[data-release="android"]', function (a) { a.href = rel.html_url; });
        setAll('[data-version="android"]', function (el) {
          el.textContent = "نسخهٔ " + toFa(version) + " · " + mb(apk.size) + " · اندروید ۷ و جدیدتر";
        });
        break;
      }

      // PixNexa Desktop: tags vX.Y.Z
      for (var j = 0; j < releases.length; j++) {
        var win = releases[j];
        if (!/^v\d/.test(win.tag_name) || win.prerelease) continue;
        var setup = findAsset(win, function (n) { return /_Setup\.exe$/i.test(n); });
        var zip = findAsset(win, function (n) { return /_Portable\.zip$/i.test(n); });
        if (!setup) continue;
        setAll('[data-dl="windows"]', function (a) { a.href = setup.browser_download_url; });
        if (zip) setAll('[data-dl="windows-portable"]', function (a) { a.href = zip.browser_download_url; });
        setAll('[data-version="windows"]', function (el) {
          el.textContent = "نسخهٔ " + toFa(win.tag_name.slice(1)) + " · " + mb(setup.size) + " · ویندوز ۱۰ و ۱۱";
        });
        break;
      }
    })
    .catch(function () { /* keep the Releases-page links */ });
})();
