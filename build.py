#!/usr/bin/env python3
"""
build.py - Generador del sitio estatico de Idiomind

Genera public/ como raíz estática del sitio, usando SourceSite/ como fuente
sin PHP ni .htaccess.

Uso:
    python3 build.py
"""

import os
import sys
import json
import shutil
import hashlib
import html
import re
import glob as globmod
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = BASE_DIR
PUBLIC_DIR = BASE_DIR.parent / "public"

# Repositorio maestro de los paquetes .idmnd. Se mantiene fuera del home
# para no duplicar cientos de MB en cada build.
IDMND_SOURCE = Path("/media/Files/Idiomind_Files")

LANGUAGES = []

SKIP_DIRS = {
    ".git", "community", "doc", "tmp", "dist", "build",
    "css", "js", "images", "share", "Files", "news",
}

SKIP_FILES_ROOT = {
    "index.php", "home.php",
    "box.php", "view.php",
    "search.php", "rss.php", "fetchfeed.php", "listen.php",
    "download.php", "upload.php", "sub.php",
    "favs.php", "json.php",
    "analyticstracking.php",
    ".htaccess", ".user.ini", "php.ini", "build.py",
}

STATIC_HTML = [
    "help.html",
    "library.html",
    "about.html",
    "donate.html",
    "maintenance.html",
    "privacypolicy.htm",
]

# Editorial content is maintained in Markdown; HTML files remain templates.
MARKDOWN_CONTENT = {
    "index.html": "content/index.md",
    "help.html": "content/help.md",
    "about.html": "content/about.md",
    "maintenance.html": "content/maintenance.md",
    "news/page1.html": "content/news/page1.md",
    "news/page2.html": "content/news/page2.md",
}

GA_SNIPPET = """<script>
  (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
  m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
  })(window,document,'script','https://www.google-analytics.com/analytics.js','ga');

  ga('create', 'UA-63037434-3', 'auto');
  ga('send', 'pageview');

</script>"""


def esc(text):
    """HTML-escape text safely."""
    return html.escape(str(text), quote=True)


def url_quote(text):
    """URL-encode a path segment, preserving / and +."""
    from urllib.parse import quote
    return quote(str(text), safe="/+'")


def find_languages():
    """Discover language directories that have subdirectories with .idmnd files."""
    langs = []
    for entry in sorted(IDMND_SOURCE.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in SKIP_DIRS:
            continue
        if entry.name.startswith("."):
            continue
        has_idmnd = any(entry.rglob("*.idmnd"))
        has_index = (entry / "index.php").exists()
        if has_index or has_idmnd:
            langs.append(entry.name)
    return langs


def find_categories(lang_dir):
    """Find subdirectories that contain .idmnd files."""
    cats = []
    if not lang_dir.is_dir():
        return cats
    for entry in sorted(lang_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        if entry.name in ("__pycache__",):
            continue
        idmnd_files = list(entry.glob("*.idmnd"))
        if idmnd_files:
            cats.append((entry.name, idmnd_files))
    return cats


def count_idmnd_in_dir(dir_path):
    """Count .idmnd files directly in a directory (not recursive)."""
    return len(list(Path(dir_path).glob("*.idmnd")))


def get_all_idmnd_recursive(lang_dir):
    """Get all .idmnd files recursively with their modification times."""
    results = []
    for f in lang_dir.rglob("*.idmnd"):
        cat = f.parent.name
        if cat == lang_dir.name:
            cat = ""
        mtime = f.stat().st_mtime
        results.append((f, cat, mtime))
    results.sort(key=lambda x: -x[2])
    return results


def generate_rss_xml(lang, categories, base_url="https://idiomind.sourceforge.io"):
    """Generate RSS XML for a language."""
    items_xml = []
    all_files = []
    for cat_name, idmnd_files in categories:
        for f in idmnd_files:
            mtime = f.stat().st_mtime
            name = f.stem
            all_files.append((f, cat_name, name, mtime))

    all_files.sort(key=lambda x: -x[3])

    for f, cat_name, name, mtime in all_files:
        dt = datetime.fromtimestamp(mtime)
        pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S %z") or dt.strftime("%a, %d %b %Y %H:%M:%S")
        cat_label = esc(cat_name.replace("-", " ").title())
        view_link = f"{base_url}/{lang}/view.html?l={url_quote(lang)}&amp;c={url_quote(cat_name)}&amp;set={url_quote(name)}"
        items_xml.append(f"""<item>
<title>{esc(name)}</title>
<link>{view_link}</link>
<pubDate>{pub_date}</pubDate>
<description>in {cat_label}</description>
</item>""")

    items_str = "\n".join(items_xml)
    now = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    return f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<atom:link href="{base_url}/{lang}/rss.xml" rel="self" type="application/rss+xml"/>
<title>Content shared by users - Idiomind</title>
<link>{base_url}/{lang}/</link>
<description>Latest Published</description>
<language>en-us</language>
<lastBuildDate>{now}</lastBuildDate>
<generator>Idiomind Build</generator>
{items_str}
</channel>
</rss>"""


def generate_latest_html(lang, categories, max_items=6):
    """Generate the 'Latest published' HTML fragment for a language."""
    all_files = []
    for cat_name, idmnd_files in categories:
        for f in idmnd_files:
            mtime = f.stat().st_mtime
            name = f.stem
            all_files.append((cat_name, name, mtime))

    all_files.sort(key=lambda x: -x[2])
    all_files = all_files[:max_items]

    html_parts = []
    for cat_name, name, mtime in all_files:
        dt = datetime.fromtimestamp(mtime)
        date_str = dt.strftime("%B %d, %Y")
        cat_label = esc(cat_name.replace("-", " ").title())
        view_link = f"/{lang}/view.html?l={url_quote(lang)}&c={url_quote(cat_name)}&set={url_quote(name)}"
        html_parts.append(f"""<div class="feed-item"><div class="feed-title"><a data-fancybox data-type="iframe" data-small-btn="true" href="{view_link}">{esc(name)}</a></div> <small><font color="#1FAF12">Published </font><font color="#626262">{date_str}</font></small></div>""")

    return "\n".join(html_parts)


def generate_category_item(lang, cat_name, count, endpoint, cls="category-item", attrs=""):
    """Build the clickable category component: name + topics count + folder icon.

    El ancla conserva `data-fancybox`/`href` para abrir exactamente el mismo
    lightbox de siempre. El enlace box.html es reescrito a
    <lang>/<category>/index.html por el post-procesado.
    """
    label = esc(cat_name.replace("-", " ").title())
    word = "topic" if count == 1 else "topics"
    prefix = f'{attrs} ' if attrs else ""
    return (
        f'<a {prefix}href="/{lang}/{endpoint}?lang={url_quote(lang)}&category={url_quote(cat_name)}" '
        f'target="_new" class="{cls}">\n'
        f'    <span class="category-name">{label}</span>\n'
        f'    <span class="category-count">{count} {word}</span>\n'
        f'    <i class="fa fa-folder-o category-icon" aria-hidden="true"></i>\n'
        f'</a>'
    )


def generate_library_header(lang, uplang):
    """Header compartido de la Library, con la misma identidad visual que el Home."""
    return f"""            <header class="site-header">
                <div class="brand">
                    <img class="brand-mark" src="/images/logo.png" alt="Idiomind logo">
                    <a class="brand-wordmark" href="/index.html">Idiomind</a>
                </div>
                <nav class="site-nav" aria-label="Main navigation">
                    <a class="site-nav-link" href="/index.html" onfocus="this.blur();">Home</a>
                    <a class="site-nav-link current" href="/{esc(lang)}/" onfocus="this.blur();">{esc(uplang)}</a>
                    <a class="site-nav-link" href="/library.html" onfocus="this.blur();">Library</a>
                    <a class="site-nav-link" href="/news/index.html" onfocus="this.blur();">News</a>
                </nav>
                <div class="site-tools">
                    <a class="site-tool" href="#" onclick="underc();return false;">Plus</a>
                    <a class="site-tool" href="#" onclick="underc();return false;"><i class="fa fa-user-o" aria-hidden="true"></i> Sign in</a>
                </div>
                <a class="site-donate" href="/donate.html">Donate</a>
            </header>

            <header class="library-head">
                <p class="page-kicker">Topic library</p>
                <h1 class="page-title">{esc(uplang)}</h1>
            </header>"""


def generate_library_category_view(lang, cat_name, idmnd_files):
    """Generate a category topic list inside the Library page."""
    rows = []

    for f in sorted(idmnd_files, key=lambda x: x.name.lower()):
        name = f.stem
        namehref = f.name
        view_url = (
            f"/{lang}/view.html"
            f"?l={url_quote(lang)}"
            f"&c={url_quote(cat_name)}"
            f"&set={url_quote(name)}"
        )
        download_url = (
            f"/{lang}/{url_quote(cat_name)}/{url_quote(namehref)}"
        )

        rows.append(f"""<tr class="library-topic-row">
            <td class="library-topic-icon">
                <a data-fancybox data-type="iframe"
                   data-small-btn="true" href="{view_url}">
                    <img src="/images/idmnd.png" alt="">
                </a>
            </td>
            <td class="library-topic-title">
                <a data-fancybox data-type="iframe"
                   data-small-btn="true" href="{view_url}">
                    {esc(name)}
                </a>
            </td>
            <td class="library-topic-download">
                <a href="{download_url}">
                    <img src="/images/dl.png" alt="Download">
                </a>
            </td>
        </tr>""")

    label = esc(cat_name.replace("-", " ").title())
    count = len(idmnd_files)
    word = "topic" if count == 1 else "topics"

    return f"""<section class="library-category-view"
                 data-lang="{esc(lang)}"
                 data-category="{esc(cat_name)}"
                 hidden>
    <div class="library-category-head">
        <div class="library-category-info">
            <h2 class="library-category-title">
                <i class="fa fa-folder-o" aria-hidden="true"></i>
                {label}
            </h2>
            <p class="library-category-count">{count} {word}</p>
        </div>
        <a class="library-category-back" href="#"
           onclick="return libCloseCategory('{esc(lang)}');">
            ← Back to {esc(lang.capitalize())}
        </a>
    </div>

    <table class="library-topic-table">
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
</section>
"""


def generate_library_page(languages_data):
    """Generate the root library.html with in-page category navigation."""
    picker_items = []
    lang_sections = []
    lang_js = []

    for lang, categories in languages_data:
        uplang = lang.capitalize()
        cat_items = []
        category_views = []
        total = 0

        for cat_name, idmnd_files in categories:
            count = len(idmnd_files)
            total += count

            if count > 0:
                label = esc(cat_name.replace("-", " ").title())
                word = "topic" if count == 1 else "topics"

                # Category navigation stays inside Library.
                cat_items.append(
                    f"""<a class="category-item" href="#"
                           onclick="return libOpenCategory('{esc(lang)}', '{esc(cat_name)}');">
                        <span class="category-name">{label}</span>
                        <span class="category-count">{count} {word}</span>
                        <i class="fa fa-folder-o category-icon" aria-hidden="true"></i>
                    </a>"""
                )

                category_views.append(
                    generate_library_category_view(
                        lang, cat_name, idmnd_files
                    )
                )

        cat_html = "\n".join(cat_items)
        category_views_html = "\n".join(category_views)
        latest = generate_latest_html(lang, categories).replace(
            ' class="btn btn-primary"', ''
        )

        word = "topic" if total == 1 else "topics"
        lang_js.append(f'"{lang}"')

        picker_items.append(f"""<li>
                    <a class="language-option"
                       data-lang="{esc(lang)}"
                       href="/{esc(lang)}/"
                       onclick="return libPick('{esc(lang)}');">
                        <span class="language-name">{esc(uplang)}</span>
                        <span class="language-count">{total} {word}</span>
                        <i class="fa fa-language language-icon" aria-hidden="true"></i>
                    </a>
                </li>""")

        lang_sections.append(f"""<section class="library-topic-view"
                                     data-lang="{esc(lang)}"
                                     hidden>
                    <header class="library-head">
                        <p class="page-kicker">Topic library</p>
                        <h1 class="page-title">{esc(uplang)}</h1>
                    </header>

                    <div class="library-language-home">
                        <p class="library-switch">
                            <a href="#" onclick="return libPick('');">
                                Change language
                            </a>
                        </p>
                        <table width="100%">
                            <tr>
                                <td valign="top">
                                    <div class="feed-lists">
                                        <h1>
                                            <i class="fa fa-bolt"
                                               aria-hidden="true"></i>
                                            Latest published
                                        </h1>
{latest}
                                    </div>
                                </td>
                                <td valign="top">
                                    <div class="fav-lists"
                                         id="favlists-{esc(lang)}"></div>
                                </td>
                            </tr>
                        </table>

                        <div class="category-grid">
{cat_html}
                        </div>
                    </div>

                    <div class="library-category-views">
{category_views_html}
                    </div>
                </section>""")

    picker_html = "\n".join(picker_items)
    sections_html = "\n".join(lang_sections)
    langs_js = ",".join(lang_js)

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN"
"http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
    <meta charset="UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">
    <meta charset="utf-8">
    <title>Idiomind | Library</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="keywords" content="learn english free, learn english online, learn english grammar, learn english vocabulary, free English lessons, english vocabulary, idiom library, ESL, EFL, pronunciation, grammar, vocabulary, tests, lessons, quiz, resources">
    <meta name="description" content="Idiomind is a valuable tool for language learners seeking to enhance their language skills. Choose the language you are learning and explore the topics shared by the community.">

    <link rel="stylesheet" type="text/css" href="/css/classic.css">
    <link rel="stylesheet" type="text/css" href="/css/fonts.css">
    <link href="/css/fa/css/font-awesome.css" rel="stylesheet" type="text/css">
    <link rel="shortcut icon" href="/favicon.ico?v=2" type="image/x-icon">

    <style>
        .library-category-views {{
            width: 100%;
        }}
        /* Keep the Library surface full-height so the footer stays at
           the bottom even when a category contains very few topics. */
        .library-category-view {{
            min-height: calc(100vh - 180px);
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
        }}

        .library-language-home {{
            min-height: calc(100vh - 180px);
            box-sizing: border-box;
        }}

        .library-category-view .library-topic-table {{
            flex: 0 0 auto;
        }}


        /* Topic viewer: compact enough to fit comfortably on laptop screens. */
        .library-viewer-frame {{
            width: 100%;
            height: 80vh !important;
            min-height: 0;
            box-sizing: border-box;
        }}

        /* Topic statistics: keep the metrics aligned to the left. */
        .topic-stats,
        .topic-meta,
        .stats {{
            text-align: left !important;
        }}

        .library-category-view {{
            width: 100%;
            box-sizing: border-box;
        }}

        .library-category-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            width: 100%;
            margin-top: 0;
            margin-bottom: 32px;
        }}

        .library-category-info {{
            display: flex;
            align-items: center;
            gap: 12px;
            min-width: 0;
        }}

        .library-category-title {{
            margin: 0;
            display: flex;
            align-items: center;
            min-width: 0;
        }}

        .library-category-count {{
            margin: 0;
            white-space: nowrap;
        }}

        .library-category-back {{
            margin-left: auto;
            white-space: nowrap;
            text-align: right;
        }}

        @media (max-width: 600px) {{
            .library-category-head {{
                align-items: flex-start;
            }}

            .library-category-info {{
                min-width: 0;
            }}

            .library-category-back {{
                white-space: normal;
            }}
        }}

        .library-category-back {{
            display: inline-block;
            margin-bottom: 12px;
            color: #666;
            text-decoration: none;
            font-size: 13px;
        }}

        .library-category-back:hover {{
            text-decoration: underline;
        }}

        .library-category-title {{
            margin: 0;
            color: #565A6E;
            font-family: Verdana, sans-serif;
            font-size: 22px;
            font-weight: normal;
            text-align: left;
        }}

        .library-category-title .fa {{
            margin-right: 7px;
        }}

        .library-category-count {{
            margin: 5px 0 0;
            color: #888;
            font-size: 13px;
            text-align: left;
        }}

        .library-topic-table {{
            width: 100%;
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            column-gap: 24px;
        }}

        .library-topic-table tbody {{
            display: contents;
        }}

        .library-topic-row {{
            display: grid;
            grid-template-columns: 48px minmax(0, 1fr) 42px;
            align-items: center;
            min-height: 58px;
            height: auto;
            border-bottom: 1px solid #e5e5e5;
        }}

        .library-topic-row td {{
            vertical-align: middle;
        }}

        .library-topic-icon {{
            width: auto;
            text-align: center;
        }}

        .library-topic-icon img {{
            width: 30px;
            height: 30px;
            vertical-align: middle;
        }}

        .library-topic-title {{
            min-width: 0;
            text-align: left;
            padding: 9px 10px;
        }}

        .library-topic-title a {{
            display: block;
            color: #565A6E;
            font-family: Verdana, sans-serif;
            font-size: 14px;
            line-height: 1.4;
            text-align: left;
            text-decoration: none;
            overflow-wrap: anywhere;
        }}

        .library-topic-title a:hover {{
            text-decoration: underline;
        }}

        .library-topic-download {{
            width: auto;
            text-align: center;
        }}

        .library-topic-download img {{
            width: 20px;
            height: 20px;
            opacity: 0.65;
            vertical-align: middle;
        }}

        .library-topic-download a:hover img {{
            opacity: 1;
        }}

        @media (max-width: 700px) {{
            .library-topic-table {{
                grid-template-columns: 1fr;
            }}
        }}

        @media (max-width: 600px) {{
            .library-topic-row {{
                grid-template-columns: 42px minmax(0, 1fr) 36px;
            }}

            .library-topic-icon img {{
                width: 26px;
                height: 26px;
            }}

            .library-topic-title {{
                padding: 8px 6px;
            }}

            .library-topic-title a {{
                font-size: 13px;
            }}
        }}
    </style>

    <script>
        if ('scrollRestoration' in history) {{
            history.scrollRestoration = 'manual';
        }}
        window.addEventListener('load', function () {{
            window.scrollTo(0, 0);
        }});
    </script>

    <script type="text/javascript">
        var LIB_COOKIE = 'language';
        var LIB_LANGS = [{langs_js}];

        function libGetCookie() {{
            var name = LIB_COOKIE + '=';
            var ca = document.cookie.split(';');

            for (var i = 0; i < ca.length; i++) {{
                var c = ca[i];
                while (c.charAt(0) == ' ') c = c.substring(1);

                if (c.indexOf(name) == 0) {{
                    try {{
                        return decodeURIComponent(
                            c.substring(name.length, c.length)
                        );
                    }} catch (e) {{
                        return c.substring(name.length, c.length);
                    }}
                }}
            }}

            return '';
        }}

        function libSetCookie(value) {{
            var d = new Date();
            d.setTime(d.getTime() + (365 * 24 * 60 * 60 * 1000));
            document.cookie =
                LIB_COOKIE + '=' + encodeURIComponent(value) +
                '; expires=' + d.toUTCString() +
                '; path=/; SameSite=Lax';
        }}

        function libGetCookieValue(name) {{
            var n = name + '=';
            var ca = document.cookie.split(';');

            for (var i = 0; i < ca.length; i++) {{
                var c = ca[i];
                while (c.charAt(0) == ' ') c = c.substring(1);

                if (c.indexOf(n) == 0) {{
                    try {{
                        return decodeURIComponent(
                            c.substring(n.length, c.length)
                        );
                    }} catch (e) {{
                        return c.substring(n.length, c.length);
                    }}
                }}
            }}

            return '';
        }}

        function libShowView(lang) {{
            var views =
                document.getElementsByClassName('library-topic-view');
            var found = false;

            for (var i = 0; i < views.length; i++) {{
                var on =
                    views[i].getAttribute('data-lang') === lang;

                views[i].hidden = !on;

                if (on) {{
                    found = true;

                    var home =
                        views[i].querySelector('.library-language-home');
                    var categories =
                        views[i].querySelector('.library-category-views');

                    if (home) home.hidden = false;
                    if (categories) categories.hidden = true;

                    var categoryViews =
                        views[i].getElementsByClassName(
                            'library-category-view'
                        );

                    for (var j = 0; j < categoryViews.length; j++) {{
                        categoryViews[j].hidden = true;
                    }}
                }}
            }}

            var picker =
                document.getElementById('library-picker');

            if (picker) picker.hidden = !!(lang && found);

            libShowPinned(lang);
        }}

        function libListFavs(lang) {{
            var faves =
                libGetCookieValue(lang.charAt(0) + 'PINS');

            if (!faves) return;

            faves = faves.split('|');

            var div =
                document.getElementById('favlists-' + lang);

            if (!div || faves.length < 1) return;

            var out =
                '<h1>Pinned ' +
                '<i class="fa fa-thumb-tack" aria-hidden="true"></i>' +
                '</h1>';

            var visibleFaves =
                Math.min(faves.length, 6);

            for (var i = 0; i < visibleFaves; i++) {{
                var fav = faves[i];
                if (!fav) continue;

                out +=
                    '<a data-fancybox data-type="iframe" ' +
                    'data-small-btn="true" ' +
                    'href="/' + lang +
                    '/view.html?l=' + lang +
                    '&c=fav&set=' + encodeURIComponent(fav) + '">' +
                    fav +
                    '</a><br>';
            }}

            div.innerHTML = out;
        }}

        function libShowPinned(lang) {{
            var views =
                document.getElementsByClassName('library-topic-view');

            for (var i = 0; i < views.length; i++) {{
                var l = views[i].getAttribute('data-lang');

                if (l && l !== lang) {{
                    var d =
                        document.getElementById('favlists-' + l);

                    if (d) d.innerHTML = '';
                }}
            }}

            if (lang) libListFavs(lang);
        }}

        function libPick(lang) {{
            if (lang) {{
                libSetCookie(lang);
                libShowView(lang);
            }} else {{
                libShowView('');
            }}

            return false;
        }}

        function libOpenCategory(lang, category) {{
            var views =
                document.getElementsByClassName('library-topic-view');
            var selectedView = null;

            for (var i = 0; i < views.length; i++) {{
                var match =
                    views[i].getAttribute('data-lang') === lang;

                views[i].hidden = !match;

                if (match) selectedView = views[i];
            }}

            if (!selectedView) return false;

            var home =
                selectedView.querySelector('.library-language-home');
            var categoryContainer =
                selectedView.querySelector('.library-category-views');

            if (home) home.hidden = true;
            if (categoryContainer) categoryContainer.hidden = false;

            var categoryViews =
                selectedView.getElementsByClassName(
                    'library-category-view'
                );

            for (var j = 0; j < categoryViews.length; j++) {{
                categoryViews[j].hidden =
                    categoryViews[j].getAttribute('data-category') !== category;
            }}

            var picker =
                document.getElementById('library-picker');

            if (picker) picker.hidden = true;

            window.scrollTo(0, 0);

            return false;
        }}

        function libCloseCategory(lang) {{
            libShowView(lang);
            return false;
        }}

        (function() {{
            function init() {{
                var saved = libGetCookie();

                if (saved) {{
                    var known = false;

                    for (var i = 0; i < LIB_LANGS.length; i++) {{
                        if (LIB_LANGS[i] === saved) {{
                            known = true;
                            break;
                        }}
                    }}

                    if (known) libShowView(saved);
                }}
            }}

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', init);
            }} else {{
                init();
            }}
        }})();
    </script>

    <script>
        var LIB_VIEWER_RETURN_LANG = '';
        var LIB_VIEWER_RETURN_CATEGORY = '';

        function libOpenViewer(href) {{
            var picker =
                document.getElementById('library-picker');
            var views =
                document.getElementsByClassName('library-topic-view');
            var viewer =
                document.getElementById('library-viewer');
            var frame =
                document.getElementById('library-viewer-frame');
            var label =
                document.getElementById('library-viewer-label');

            var url = new URL(href, window.location.href);
            var category = url.searchParams.get('c');

            LIB_VIEWER_RETURN_LANG =
                url.searchParams.get('l') || '';

            LIB_VIEWER_RETURN_CATEGORY =
                category || '';

            if (!category) {{
                var parts =
                    url.pathname.split('/').filter(Boolean);

                category =
                    parts[parts.length - 1] === 'index.html'
                    ? parts[parts.length - 2]
                    : '';
            }}

            category =
                decodeURIComponent(category || '')
                .replace(/[-_]+/g, ' ');

            if (category === 'fav') {{
                category = 'Pinned';
            }} else if (category) {{
                category = category.replace(
                    /\\b\\w/g,
                    function(letter) {{
                        return letter.toUpperCase();
                    }}
                );
            }}

            if (label) {{
                label.textContent = category || 'Topic viewer';
            }}

            for (var i = 0; i < views.length; i++) {{
                views[i].hidden = true;
            }}

            if (picker) picker.hidden = true;

            if (viewer && frame) {{
                frame.onload = function() {{
                    try {{
                        var scrollbarStyle =
                            frame.contentDocument.createElement('style');

                        scrollbarStyle.textContent =
                            'html {{ scrollbar-width: none; }} ' +
                            'html::-webkit-scrollbar {{ width: 0; height: 0; }}';

                        frame.contentDocument.head.appendChild(
                            scrollbarStyle
                        );

                        var nestedLinks =
                            frame.contentDocument.querySelectorAll(
                                'a[href*="/view.html"]'
                            );

                        for (var i = 0; i < nestedLinks.length; i++) {{
                            nestedLinks[i].onclick = function(event) {{
                                event.preventDefault();
                                window.parent.libOpenViewer(this.href);
                                return false;
                            }};
                        }}
                    }} catch (error) {{
                        console.error(
                            'Unable to bind embedded library links',
                            error
                        );
                    }}
                }};

                frame.src =
                    href +
                    (href.indexOf('?') === -1 ? '?' : '&') +
                    'v=20260911';

                viewer.hidden = false;
                window.scrollTo(0, 0);
            }}

            return false;
        }}

        function libCloseViewer() {{
            var viewer =
                document.getElementById('library-viewer');
            var frame =
                document.getElementById('library-viewer-frame');

            if (frame) frame.src = 'about:blank';
            if (viewer) viewer.hidden = true;

            var saved = libGetCookie();

            if (LIB_VIEWER_RETURN_LANG &&
                LIB_VIEWER_RETURN_CATEGORY &&
                LIB_VIEWER_RETURN_CATEGORY !== 'fav') {{
                libOpenCategory(
                    LIB_VIEWER_RETURN_LANG,
                    LIB_VIEWER_RETURN_CATEGORY
                );
            }} else if (saved) {{
                libShowView(saved);
            }} else {{
                var picker =
                    document.getElementById('library-picker');

                if (picker) picker.hidden = false;
            }}

            LIB_VIEWER_RETURN_LANG = '';
            LIB_VIEWER_RETURN_CATEGORY = '';

            return false;
        }}

        document.addEventListener('click', function(event) {{
            var link = event.target;

            while (link && link.tagName !== 'A') {{
                link = link.parentElement;
            }}

            if (!link) return;

            var href =
                link.getAttribute('href') || '';

            if (link.hasAttribute('data-fancybox')) {{
                event.preventDefault();
                libOpenViewer(href);
            }}
        }});
    </script>

    {GA_SNIPPET}
</head>

<body>

    <div class="library-main">

        <header class="site-header">
            <div class="brand">
                <img class="brand-mark"
                     src="/images/logo.png"
                     alt="Idiomind logo">
                <a class="brand-wordmark"
                   href="/index.html">
                    Idiomind
                </a>
            </div>

            <nav class="site-nav" aria-label="Main navigation">
                <a class="site-nav-link"
                   href="index.html"
                   onfocus="this.blur();">
                    Introduction
                </a>
                <a class="site-nav-link"
                   href="help.html"
                   onfocus="this.blur();">
                    Getting started
                </a>
                <a class="site-nav-link current"
                   href="library.html"
                   onfocus="this.blur();">
                    Library
                </a>
                <a class="site-nav-link"
                   href="/news/index.html"
                   onfocus="this.blur();">
                    News
                </a>
            </nav>

            <a class="site-donate"
               href="/donate.html">
                Donate
            </a>
        </header>

        <section id="library-picker"
                 class="language-picker">
            <header class="library-head">
                <p class="page-kicker">Idiomind library</p>
                <h1 class="page-title">
                    Choose the language you are learning
                </h1>
                <p class="page-lead">
                    Select the language you are learning to browse the
                    topics shared by the community. Your choice is remembered
                    on this device.
                </p>
            </header>

            <ul class="language-list">
{picker_html}
            </ul>
        </section>

{sections_html}

        <section id="library-viewer"
                 class="library-viewer"
                 hidden>
            <div class="library-viewer-head">
                <p id="library-viewer-label"
                   class="library-viewer-label">
                    Topic viewer
                </p>
                <a id="library-viewer-back"
                   class="library-viewer-back"
                   href="#"
                   onclick="return libCloseViewer();">
                    Back to library
                </a>
            </div>

            <iframe id="library-viewer-frame"
                    class="library-viewer-frame"
                    title="Topic viewer"
                    loading="lazy"
                    scrolling="yes"></iframe>
        </section>

        <footer class="site-footer">
            <p>
                &copy; 2026
                <a href="https://idiomind.sourceforge.io">
                    Idiomind Project
                </a>
            </p>
        </footer>

    </div>

</body>
</html>
"""



def generate_lang_index(lang, categories):
    """Generate the main home page for a language."""
    uplang = lang.capitalize()
    cat_boxes = []
    for cat_name, idmnd_files in categories:
        count = len(idmnd_files)
        if count > 0:
            cat_boxes.append(generate_category_item(
                lang, cat_name, count, "box.html",
                attrs='data-fancybox data-type="iframe" data-small-btn="true"'))

    categories_html = "\n".join(cat_boxes)
    latest = generate_latest_html(lang, categories)

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"/>

<head>
    <meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <meta name="description" content=""/>
    <meta name="author" content=""/>
    <meta name="keywords" content="ESL, EFL, pronunciation, grammar, vocabulary, tests, lessons, quiz, quizzes, resources, lesson, vocabulary, questions, answers"/>
    <meta name="description" content="Learn foreign vocabulary"/>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <link rel="shortcut icon" href="/favicon.ico?v=2" type="image/x-icon">
    <link rel="icon" type="image/png" href="/favicon-32x32.png" sizes="32x32" />
    <link rel="icon" type="image/png" href="/favicon-16x16.png" sizes="16x16" />
    <link rel="image_src" href="https://idiomind.sourceforge.io/images/logo.png" />
    <title>Idiomind's library</title>
    <link href="/css/home.css" rel="stylesheet" type="text/css" />
    <link href="/css/fa/css/font-awesome.css" rel="stylesheet" type="text/css" />
    <link rel="stylesheet" type="text/css" href="/js/fancybox/jquery.fancybox.css" media="screen" />

    <script>
        if ('scrollRestoration' in history) {{
            history.scrollRestoration = 'manual';
        }}
        window.addEventListener('load', function () {{
            window.scrollTo(0, 0);
        }});
    </script>

    <script type="text/javascript">
        function setCookie() {{
            var d = new Date();
            d.setTime(d.getTime() + (30*24*60*60*1000));
            var expires = "expires=" + d.toGMTString();
            document.cookie="language={esc(lang)}; expires=" + expires + "; path=/";
        }}
    </script>

    <script type="text/javascript">
        function getCookie(cname) {{
            var name = cname + "=";
            var decodedCookie = decodeURIComponent(document.cookie);
            var ca = decodedCookie.split(';');
            for(var i = 0; i <ca.length; i++) {{
                var c = ca[i];
                while (c.charAt(0) == ' ') {{
                    c = c.substring(1);
                }}
                if (c.indexOf(name) == 0) {{
                    return c.substring(name.length, c.length);
                }}
            }}
            return "";
        }}

        function ListFavs() {{
            var fav;
            var lang = "{esc(lang)}";
            var faves = getCookie(lang.charAt(0)+'PINS');
            faves = faves.split('|');
            var div = document.getElementById('favlists');
            if(faves.length > 1) {{
                div.innerHTML = "<br><h1 style='text-align:right'>Pinned <i class='fa fa-thumb-tack' aria-hidden='true'></i></h1><br>";
                for (fav of faves) {{
                    div.innerHTML = div.innerHTML + '<a data-fancybox data-type="iframe" class="btn btn-primary"  data-small-btn="true" href="/{esc(lang)}/view.html?l={esc(lang)}&c=fav&set='+fav+'">'+fav+'</a><br><br>';
                }}
            }}
            else {{
                div.innerHTML = "";
            }}
        }}
    </script>

    <script src="//code.jquery.com/jquery-3.2.1.min.js"></script>
    <script type="text/javascript" src="/js/fancybox/jquery.fancybox.js"></script>

    <script type="text/javascript">
    function underc(){{
        alert('This website is under construction');
    }}

    function hideshow(which){{
        if (!document.getElementById)
        return
        if (which.style.display=="block")
        which.style.display="none"
        else
        which.style.display="block"
    }}

    function hideshowSearchbox(which){{
        if (!document.getElementById)
        return
        if (which.style.display=="block")
        which.style.display="none"
        else
        which.style.display="block"
    }}
    var searchBox = `
    <div class="SearchDiv">
        <div style="width:99%;margin-top:5px;align:right;text-align:right"><a href="javascript:hideshow(document.getElementById('searchBox'))"><img src="/images/close.png"></img></a></div>
           <form action="/search.html" method="get">
            <input name="q" value=""/>
            <input type="submit" value="Search"/>
            </form>
    </div>
    <br>
    `;
    $(document).ready(function(){{
        $("#showSearch").click(function(){{
            document.getElementById('searchBox').innerHTML = searchBox;
            document.getElementById('searchBox').style.display="block"
        }});
    }});
</script>

    {GA_SNIPPET}
</head>


<body onload="setCookie()">

    <main id="content" class="group" role="main">
        <div class="main">

            <!-- Header (misma identidad visual que el Home) -->
            {generate_library_header(lang, uplang)}

            <!-- plus & searchBox -->
            <div id="plus"></div>
            <div id="searchBox"></div>

            <!-- Note -->
            <div class="sentenceweek">
                <div class="sentencew-content">
                    <div class="comment more"><br></div><table id="excelDataTable" border="0"></table>
                </div>
            </div>
            <br>

            <!-- Feeds and favs -->
            <table width='100%'>
                <tr>
                    <td valign="top">
                        <div class="feed-lists">
                            <br><h1><i class="fa fa-bolt" aria-hidden="true"></i> Latest published</h1><br>
                            {latest}
                        </div>
                    </td>
                    <td valign="top">
                        <div class="fav-lists" id="favlists"></div>
                    </td>
                </tr>
            </table>

             <!-- Folders -->
            <div id="categories">
                {categories_html}
            </div>
        </div>
      <br>
    </main>

    <footer class="footer">
        <br>
        <div> &copy 2015-2026 <a href="https://idiomind.sourceforge.io">idiomind</a> Project | <a href="../privacypolicy.htm">Privacy</a><br><a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">All the content is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike</a>.
        </div>
        <br>
    </footer>
</body>

<script type="text/javascript">
    $(document).ready(function() {{

            function getCookie(cname) {{
                var name = cname + "=";
                var decodedCookie = decodeURIComponent(document.cookie);
                var ca = decodedCookie.split(';');
                for(var i = 0; i <ca.length; i++) {{
                    var c = ca[i];
                    while (c.charAt(0) == ' ') {{
                        c = c.substring(1);
                    }}
                    if (c.indexOf(name) == 0) {{
                        return c.substring(name.length, c.length);
                    }}
                }}
                return "";
            }}

        var showChar = 100;
        var ellipsestext = "...";
        var moretext = " More";
        var lesstext = " Less";
        $('.more').each(function() {{
            var content = "Please note: this web site is a work in progress. Not all sections are complete - many have not even been started yet. Not all links work.  If you've arrived on this site, feel free to enjoy what's here, and check back for further additions if you wish, knowing it will take some time before the site is finished."

            if(content.length > showChar) {{
                var c = content.substr(0, showChar);
                var h = content.substr(showChar-1, content.length - showChar);
                var html = c + '<span class="moreellipses">' + ellipsestext+ '&nbsp;</span><span class="morecontent"><span>' + h + '</span>&nbsp;&nbsp;<a href="" class="morelink">' + moretext + '</a></span>';
                $(this).html(html);
            }}
        }});

        $(".morelink").click(function(){{
            if($(this).hasClass("less")) {{
                $(this).removeClass("less");
                $(this).html(moretext);

            }} else {{
                $(this).addClass("less");
                $(this).html(lesstext);
            }}
            $(this).parent().prev().toggle();
            $(this).prev().toggle();
            return false;
        }});
    }});

</script>

<script type="text/javascript">ListFavs();</script>

</html>
"""


def generate_box(lang, cat_name, idmnd_files):
    """Generate the category listing page (box)."""
    rows = []
    for f in sorted(idmnd_files, key=lambda x: x.name.lower()):
        name = f.stem
        namehref = f.name
        rows.append(f"""<tr id="box">
            <td style="width:5%"><a href="/{lang}/view.html?l={url_quote(lang)}&c={url_quote(cat_name)}&set={url_quote(name)}"><img class='expand' src='/images/idmnd.png'></a></td>
            <td style="width:90%"><a href="/{lang}/view.html?l={url_quote(lang)}&c={url_quote(cat_name)}&set={url_quote(name)}">{esc(name)}</a></td>
            <td style="width:5%"><a href="/{lang}/{url_quote(cat_name)}/{url_quote(namehref)}"><img src='/images/dl.png'></a></td>
        </tr>""")

    rows_html = "\n".join(rows)

    return f"""<!doctype html>
<html>
<head>
  <meta charset="UTF-8">
 <meta charset="UTF-8">
   <link rel="shortcut icon" href="/favicon.ico">
   <title>Topics</title>
   <link rel="stylesheet" href="/css/box.css">
</head>

<body>
<div id="container">

    <table class="sortable">
        <thead>
        <tr>
        </tr>
        </thead>
        <tbody>
{rows_html}
        </tbody>
    </table>

</div>
</body>"""


def generate_view(lang, css_file="/css/view.css", js_file="/js/view.js"):
    """Generate the view page (flashcards/quiz/viewer)."""
    return f"""<html lang="en">
    <head>
       <meta charset="UTF-8">
 <meta charset="utf-8"/>
        <title>Study</title>
        <meta name="description" content="Flashcards"/>
        <link rel="stylesheet" href="{css_file}"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <link rel="stylesheet" href="/css/sweetalert.css"/>

        <style>
            #TopicLanding {{
                width: 100%; max-width: 1100px; margin: 0 auto;
                box-sizing: border-box; padding: 0 2vw 2vw;
            }}
            #TopicLanding .TestStartBtn {{ margin-bottom: 14px; }}
            #TopicLanding .topic-details {{
                width: 100%; box-sizing: border-box; margin: 0 0 16px;
                padding: 10px 12px; border-top: 1px solid #d8d8d4;
                border-bottom: 0px solid #d8d8d4; color: #5a5a5a;
                font-size: 14px; line-height: 1.6;
            }}
            #TopicLanding .topic-level,
            #TopicLanding .topic-content,
            #TopicLanding .topic-meta {{ margin: 2px 0; }}
            #TopicLanding .topic-level b {{ color: #464b5f; font-weight: 600; }}
            #TopicLanding .topic-note {{
                width: 100%; min-height: 150px; box-sizing: border-box;
                padding: 20px 22px; background: #f7f7f5;
                border: 1px solid #d4d4d0; border-radius: 4px;
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
                color: #4a4a4a; text-align: left;
            }}
            #TopicLanding .topic-note p {{
                margin: 0; color: #4a4a4a; line-height: 1.6; white-space: pre-wrap;
            }}
            /* Flashcard score: text only, with colored underline. */
            #headB .flascards_info {{
                background: transparent !important;
                border: 0 !important;
                box-shadow: none !important;
                margin: 0 !important;
                padding: 0 !important;
            }}

            #headB .flascards_info td {{
                background: transparent !important;
                border: 0 !important;
                padding: 0 !important;
            }}

            #headB #score_no,
            #headB #score_ok {{
                display: inline-block !important;
                padding: 0 0 5px !important;
                margin: 0 28px 0 0 !important;
                background: transparent !important;
                border: 0 !important;
                border-radius: 0 !important;
                box-shadow: none !important;
                color: #474747 !important;
                font-weight: 700 !important;
                text-align: left !important;
                line-height: 1.3;
                border-bottom: 3px solid !important;
            }}

            #headB #score_no {{
                border-bottom-color: #d9534f !important;
            }}

            #headB #score_ok {{
                border-bottom-color: #4caf50 !important;
            }}

            #headB #score_no font,
            #headB #score_ok font {{
                color: #474747 !important;
                font-weight: 700 !important;
            }}

            @media (max-width: 600px) {{
                #TopicLanding {{ padding: 0 12px 16px; }}
                #TopicLanding .topic-details {{ font-size: 13px; padding: 9px 10px; }}
                #TopicLanding .topic-note {{ min-height: 120px; padding: 16px; }}
            }}
        </style>

        <script>
            if ('scrollRestoration' in history) {{
                history.scrollRestoration = 'manual';
            }}
            window.addEventListener('load', function () {{
                window.scrollTo(0, 0);
            }});
        </script>

        <script type="text/javascript"> //  Loading gif
            function showLoading() {{
                var loadingEl = document.getElementById('loading');
                var pageEl = document.getElementById('page');
                if (loadingEl) loadingEl.style.display = 'block';
                if (pageEl) pageEl.style.display = 'none';
            }}

            function hideLoading() {{
                var loadingEl = document.getElementById('loading');
                var pageEl = document.getElementById('page');
                if (loadingEl) loadingEl.style.display = 'none';
                if (pageEl) pageEl.style.display = 'block';
            }}

            showLoading();
        </script>

        <script type="text/javascript"> // Image fix
            function imgError(image) {{
                image.onerror = "";
                image.style="display: none;";
                var s = document.getElementById("imgs");
                s.value = "<br>";
                return true;
            }}
        </script>

         <script type="text/javascript"> // Get X cookie value
            function getCookie(cname) {{
                var name = cname + "=";
                var decodedCookie = decodeURIComponent(document.cookie);
                var ca = decodedCookie.split(';');
                for(var i = 0; i <ca.length; i++) {{
                    var c = ca[i];
                    while (c.charAt(0) == ' ') {{
                        c = c.substring(1);
                    }}
                    if (c.indexOf(name) == 0) {{
                        return c.substring(name.length, c.length);
                    }}
                }}
                return "";
            }}
         </script>

        <script type="text/javascript"> //  Buttons fav & lesson at loading
        function setBtnFav() {{
            var lang = "{esc(lang)}";
            var cookie_name = lang.charAt(0)+'PINS';
            var div = document.getElementById("data-name");
            var tpc = div.textContent;
            tpc = tpc.replace(/(^[ \\t]*\\n)/gm, '').replace(/^\\s\\s*/, '').replace(/\\s\\s*$/, '');
            /* Favorite */
            var el = document.getElementById("FavBtn")
            var faves = getCookie(cookie_name);
            var bol = faves.includes(tpc);
            if(bol == false) {{ el.src='/images/fav.png'; }}
            else {{ el.src='/images/unfav.png'; }}
        }}
        </script>

        <script type="text/javascript"> //  Toggle Button fav
            function Favesjs(el) {{
                var lang = "{esc(lang)}";
                var cookie_name = lang.charAt(0)+'PINS';
                var faves = getCookie(cookie_name);
                var bol = faves.includes(currentTopicData.name);

                if(bol == true)
                {{
                    var SetFavs_value = faves.replace(currentTopicData.name+'|','');
                    var expiration_date = new Date();
                    expiration_date.setFullYear(expiration_date.getFullYear() + 1);
                    var expires = "expires=" + expiration_date.toGMTString();
                    document.cookie=cookie_name+"="+SetFavs_value+"; expires=" + expires + "; path=/";
                    el.src='/images/fav.png';
                }}
                else
                {{
                    SetFavs_value = currentTopicData.name+'|'+faves
                    var expiration_date = new Date();
                    expiration_date.setFullYear(expiration_date.getFullYear() + 1);
                    var expires = "expires=" + expiration_date.toGMTString();
                    document.cookie=cookie_name+"="+SetFavs_value+"; expires=" + expires + "; path=/";
                    el.src='/images/unfav.png';
                }}
            }}
        </script>

        <script type="text/javascript"> //  Toggle Button study
            function StudySet(el) {{
                var lessonChk = getCookie('topic_study');

                if(currentTopicData.name == lessonChk)
                {{
                    var expiration_date = new Date();
                    expiration_date.setFullYear(expiration_date.getFullYear() + 1);
                    var expires = "expires=" + expiration_date.toGMTString();
                    document.cookie="topic_study="+SetFavs_value+"; expires=" + expires + "; path=/";
                    el.src='/images/pin.png';
                }}
                else
                {{
                    SetFavs_value = currentTopicData.name
                    var expiration_date = new Date();
                    expiration_date.setFullYear(expiration_date.getFullYear() + 1);
                    var expires = "expires=" + expiration_date.toGMTString();
                    document.cookie="topic_study="+SetFavs_value+"; expires=" + expires + "; path=/";
                    el.src='/images/unpin.png';
                }}
            }}
        </script>

    </head>
    <body onload="setBtnFav()">
        <div id="audio"></div>
        {GA_SNIPPET}
         <div id="data-name" style="display:none;">
        </div>
        <div id="dom-target" style="display:none;">
        </div>

 <div id="page">

    <span id="headA">
        <table style="width:100%;margin:0;vertical-align:top;">
            <tr>
                <td>
                    <div id="name" class="topicName">
                        <h1 style="font-weight:bold;font-family:Verdana;font-size:20px;font-size:1.50vw;"></h1>
                    </div>
                </td>
                <td class="floating-box-right"><div><a href="##" id="goBack"><img title='Go back' src='/images/back_grey.png'></a></div></td>
            </tr>
        </table>
    </span>

    <span id="headB" style="visibility:hidden">
        <table style="width:100%;margin:0;vertical-align:top;">
            <tr>
                <td>

				<table class="flascards_info">
					<tr>
						<td>
							<span id="score_no" class="score score-no">
								I did not know it: <font></font>
							</span>
							&nbsp;&nbsp;&nbsp;
							<span id="score_ok" class="score score-ok">
								I knew it: <font></font>
							</span>
						</td>
					</tr>
					<tr>
						<td>
							<span style="text-align:left;"><font></font></span>
						</td>
					</tr>
				</table>

                <td>
                </td>
                <td class="floating-box-right"><div><a href="##" id="ToHomeB"><img src='/images/close.png'></a></div></td>
            </tr>
        </table>
    </span>

    <span id="headC" style="visibility:hidden">
        <table border="0" style="width:100%;margin:0;vertical-align:top;">
        <tr>
        <td>
            <table border="0" class="viewer_info">
                <tr>
                    <td>
                        <span style="text-align:left;"><font></font></span>
                        <span class="slidecontainer" id="slidecontainer" style="visibility:hidden;">
                        <input type="range" min="1" max="200" value="1" class="slider" id="item_slider">
                        </span>
                    </td>
                </tr>
                <tr>
                    <td style="visibility:hidden">
                        <span id="total"> total <font color="#1B5EC0"></font></span> /
                        <span id="item"><font color="#464B5F">1</font></span>
                    </td>
                </tr>
                </td>
            </table>
            <td>
            </td>
            <td class="floating-box-right"><div><a href="##" id="ToHomeC"><img src='/images/close.png'></a></div></td>
            </tr>
        </table>
    </span>

    <span id="TopicLanding">
        <div class="TestStartBtn">
            <input type="image" src="/images/fav.png" class="fav" style="outline:none;" id="FavBtn" onclick="Favesjs(this);" />
            <input title="Flashcards" type="image" src="/images/flashc1.png" class="flashdef" style="outline:none;" id="flashdef" />
        </div>

        <div class="topic-details">
            <div class="topic-level">
                <span id="levl">This topic is aimed for <b><font></font></b> students.</span>
            </div>
            <div class="topic-content">
                <span>Contains: </span>
                <span id="nwrd"><font></font></span>
                <span id="nsnt"><font></font></span>
                <span id="naud"><font></font></span>
                <span id="nimg"><font></font></span>
            </div>
            <div class="topic-meta">
                Translations: <span id="slng"><font></font></span><br>
                It was uploaded on <span id="dteu"><font></font></span>
                <span id="autr"> by <font></font>.
                    <b><a href="#" id="downloadLink">Download</a></b>
                </span>
            </div>
        </div>

        <div class="topic-note" id="info_note">
            <p></p>
        </div>
    </span>

    <div id="fscreen">

            <div id="imgs">
                <p></p>
            </div>

            <a href="##" id="tts"  title="Click to listen" style="text-decoration:none;" onclick="doFunction();">

                <div class="trgt pronounce" id="trgt">
                    <h1 style="color:#4A4A4A"></h1>
                </div>
            </a>

            <div id="srce">
                <h2 style="color:#758571;"></h2>
            </div>
            <div id="dots">
                <h2 style="color:#677862"></h2>
            </div>

            <div class="exmp" id="exmp">
                <p></p>
            </div>

        </div>

        <div id="vscreen">

            <div id="v_imgs">
                <p></p>
            </div>

            <a href="##" id="vtts" title="Click to listen" style="text-decoration:none;" onclick="doFunction();">

                <div class="grmr pronounce" id="grmr">
                    <h1 style="color:#4A4A4A"></h1>
                </div>

            </a>

            <div id="v_srce">
                <h2 style="color:#79848F;"></h2>
            </div>

            <div class="exmp" id="v_exmp">
                <p></p>
            </div>

            <div id="trgt">
                    <p style="color:#4A4A4A"></p>
            </div>

        </div>

        <div id="QuizButtons" class="QuizButtons" style="visibility:hidden;">
                <input class="btnNo" id="Wrong" type="button" value="No" onclick="doFunction();" />
                <input style="display: inline-block;" class="btnShow" id="Show" type="button" value="Show translation" onclick="doFunction();" />
                <input class="btnOk" id="Right" type="button" value="OK" onclick="doFunction();" />
        </div>

        <div class="center">
            <table border="0" id="ViewerButtons" class="ViewerButtons" style="visibility:hidden;">
                <tr>
                    <td><input class="btnBack" style="background:url(/images/back1.png);background-repeat:no-repeat;background-position:center;outline:none;" id="Back" type="button" onclick="doFunction();" /></td>
                    <td><input type="image" src="/images/play.png" class="btnPlay" style="background-position:center;outline:none;" id="Play" onclick="doFunction();" /></td>
                    <td><input class="btnNext" style="background:url(/images/next1.png);background-repeat:no-repeat;background-position:center;outline:none;" id="Next" type="button" onclick="doFunction();" /></td>
                </tr>
            </table>
        </div>

</div>

<div id="loading"></div>

</body>

<script type="text/javascript" src="{js_file}"></script>
<script>
    var params = new URLSearchParams(window.location.search);
    var lang = params.get('l') || '{esc(lang)}';
    var cat = params.get('c') || '';
    var set = params.get('set') || '';
    var myData = '/' + lang + '/' + cat + '/' + set + '.idmnd';

    var div = document.getElementById("data-name");
    div.textContent = set;
    var domTarget = document.getElementById("dom-target");
    domTarget.textContent = myData;

    // Go back link
    document.getElementById("goBack").href = "/" + lang + "/" + decodeURIComponent(cat) + "/index.html";
    // Download link
    document.getElementById("downloadLink").href = myData;

    Topic.loadData(myData);
</script>

</html>"""


def generate_favs(lang):
    """Generate the favorites page (100% JavaScript)."""
    return f"""<!doctype html>
<html>
<head>
  <meta charset="UTF-8">
 <meta charset="UTF-8">
   <link rel="shortcut icon" href="/favicon.ico">
   <title>Topics</title>
   <link rel="stylesheet" href="/css/box.css">
</head>

<body>
<div id="container">

    <table class="sortable">
        <thead>
        <tr>
        </tr>
        </thead>
        <tbody id="favsBody">
        </tbody>
    </table>
</div>
<script>
(function() {{
    var lang = "{esc(lang)}";
    var cookie_name = lang.charAt(0) + 'PINS';
    var faves = "";
    var decodedCookie = decodeURIComponent(document.cookie);
    var ca = decodedCookie.split(';');
    for (var i = 0; i < ca.length; i++) {{
        var c = ca[i];
        while (c.charAt(0) == ' ') c = c.substring(1);
        if (c.indexOf(cookie_name + '=') == 0) {{
            faves = c.substring(cookie_name.length + 1);
            break;
        }}
    }}
    if (!faves) return;
    var parts = faves.split('|');
    var tbody = document.getElementById('favsBody');
    for (var i = 0; i < parts.length; i++) {{
        var fav = parts[i];
        if (fav && fav !== '|') {{
            var tr = document.createElement('tr');
            tr.id = 'box';
            tr.innerHTML = '<td style="width:5%"><a href="/{esc(lang)}/view.html?l={esc(lang)}&c=fav&set=' + encodeURIComponent(fav) + '"><img class="expand" src="/images/idmnd.png"></a></td>' +
                '<td style="width:90%"><a href="/{esc(lang)}/view.html?l={esc(lang)}&c=fav&set=' + encodeURIComponent(fav) + '">' + fav + '</a></td>';
            tbody.appendChild(tr);
        }}
    }}
}})();
</script>
</body>
</html>"""


def generate_root_index():
    """Generate the root index.html page."""
    return """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head><meta charset="UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">
    <meta charset="utf-8">
    <title>Idiomind</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="keywords" content="learn english free, learn english, learn english online, learn english grammar, learn english vocabulary, free English lessons, basic english, english vocabulary, english dictation, business english, english as a second language, english as a foreign language, english spelling, english grammar, english dictation, ESL, EFL, pronunciation, grammar, vocabulary, tests, lessons, quiz, quizzes, resources, lesson, vocabulary, questions, answers"/>
    <meta name="description" content="Idiomind is a valuable tool for language learners seeking to enhance their language skills."/>

    <link rel="stylesheet" type="text/css" href="/css/classic.css">
    <link rel="stylesheet" type="text/css" href="/css/fonts.css">

    <link rel="shortcut icon" href="/favicon.ico?v=2" type="image/x-icon">
    <link rel="icon" type="image/png" href="favicon-32x32.png" sizes="32x32"/>
    <link rel="icon" type="image/png" href="favicon-16x16.png" sizes="16x16"/>
    <link rel="image_src" href="/images/logo.png"/><!--formatted-->

    <script>
      (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
      (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
      m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
      })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

      ga('create', 'UA-63037434-3', 'auto');
      ga('send', 'pageview');
    </script>

    <script type="text/javascript">
        function googleTranslateElementInit() {
            new google.translate.TranslateElement({pageLanguage: 'en', includedLanguages: 'da,de,el,en,es,fr,hr,hu,id,it,iw,ko,nl,pl,pt,ru,tr,uk,zh-CN,zh-TW', layout: google.translate.TranslateElement.InlineLayout.HORIZONTAL}, 'google_translate_element');
        }
    </script>

    <script ="text/javascript" src="//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>


</head>

<body>

    <div class="wrapper">

        <header class="site-header">
            <div class="brand">
                <img class="brand-mark" src="/images/logo.png" alt="Idiomind logo">
                <a class="brand-wordmark" href="/index.html">Idiomind</a>
            </div>
            <nav class="site-nav" aria-label="Main navigation">
                <a class="site-nav-link current" href="index.html" onfocus="this.blur();">Introduction</a>
                <a class="site-nav-link" href="help.html" onfocus="this.blur();">Getting started</a>
                <a class="site-nav-link" href="library.html" onfocus="this.blur();">Library</a>
                <a class="site-nav-link" href="/news/index.html" onfocus="this.blur();">News</a>
            </nav>
            <a class="site-donate" href="/donate.html">Donate</a>
        </header>

        <main class="page-main">

            <section class="hero">
                <p class="hero-kicker">A quiet place for the words you learn</p>
                <h1 class="hero-title">Idiomind</h1>
                <p class="hero-lead">
                    Keep the words and phrases you come across every day, review them, and make them yours — in up to ten languages.
                </p>
                <div class="hero-actions">
                    <a class="btn btn-primary" href="/library.html">Explore the library</a>
                    <a class="btn btn-ghost" href="#install">Get Idiomind</a>
                </div>
            </section>

            <section class="prose">
                <p>
                    Language learners are always in search of new words and phrases. Idiomind can assist you in your language learning journey by allowing you to save and practice the words and phrases you come across every day.
                </p>
            </section>

            <section class="features">
                <h2 class="section-title">Features</h2>
                <ul class="features-list">
                    <li>Take notes on the go</li>
                    <li>Words and phrases pronunciation</li>
                    <li>Automatic translation using Google Translate</li>
                    <li>Practices</li>
                    <li>Track your progress through reviews to reinforce your learning</li>
                    <li>Customize up to 10 languages to learn</li>
                    <li>User-friendly interface available in English, Spanish, Portuguese, French, and Italian</li>
                </ul>
            </section>

            <section class="usage">
                <h2 class="section-title">Usage example</h2>
                <p class="section-note">
                    Taking note of words and sentences from a PDF document. Here is an example of how to take notes on words and sentences from a PDF document using Idiomind:
                </p>
                <div class="media-frame">
                    <iframe width="285" height="160" src="https://www.youtube.com/embed/HFvcQjlVHcA?rel=0&showinfo=0" frameborder="0" allowfullscreen></iframe>
                </div>
            </section>

            <section class="install" id="install">
                <h2 class="section-title">Install / Download</h2>
                <p class="section-note">You can install Idiomind through the terminal using the following commands:</p>
                <pre><code>add-apt-repository ppa:robinpalat/idiomind
apt-get update
apt-get install idiomind</code></pre>
                <p class="section-note">
                    Alternatively, you can download it from SourceForge. However, the recommended method is to use the above commands for installation.
                </p>
                <a href="https://sourceforge.net/projects/idiomind/files/latest/download"><img alt="Download Idiomind" src="https://a.fsdn.com/con/app/sf-download-button" width=276 height=48 srcset="https://a.fsdn.com/con/app/sf-download-button?button_size=2x 2x"></a>
            </section>

        </main>

    </div>

    <footer class="site-footer">
        <p>&copy; 2026 <a href="https://idiomind.sourceforge.io">Idiomind Project</a></p>
    </footer>

</body>

</html>
"""


def generate_search():
    """Generate the search page and search index."""
    search_html = """<!DOCTYPE html>
<html>
<head>
   <meta charset="UTF-8">
 <meta charset="utf-8">
    <title>Idiomind - Search</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" type="text/css" href="/css/classic.css">
    <link rel="stylesheet" type="text/css" href="/css/fonts.css">
    <link rel="shortcut icon" href="/favicon.ico?v=2" type="image/x-icon">
    <style>
        .search-box { max-width: 600px; margin: 40px auto; padding: 20px; }
        .search-input { width: 100%; padding: 10px; font-size: 16px; border: 2px solid #ccc; border-radius: 4px; }
        .search-results { max-width: 600px; margin: 20px auto; }
        .search-result { padding: 10px; border-bottom: 0px solid #eee; }
        .search-result a { color: #333; text-decoration: none; font-size: 16px; }
        .search-result a:hover { text-decoration: underline; }
        .search-result .lang { color: #888; font-size: 12px; }
        .search-result .cat { color: #666; font-size: 13px; }
    </style>
</head>
<body>
    <div class="search-box">
        <h2>Search Topics</h2>
        <input type="text" id="searchInput" class="search-input" placeholder="Type to search..." autofocus>
    </div>
    <div class="search-results" id="searchResults"></div>

    <script>
    (function() {
        var index = null;
        var input = document.getElementById('searchInput');
        var results = document.getElementById('searchResults');

        // Check URL params for initial query
        var params = new URLSearchParams(window.location.search);
        var q = params.get('q');
        if (q) {
            input.value = q;
        }

        fetch('/search-index.json')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                index = data;
                if (q) doSearch(q);
            });

        input.addEventListener('input', function() {
            var val = input.value.trim();
            if (val.length < 2) {
                results.innerHTML = '';
                return;
            }
            doSearch(val);
        });

        function doSearch(query) {
            if (!index) return;
            var lq = query.toLowerCase();
            var html = '';
            var count = 0;
            for (var i = 0; i < index.length; i++) {
                var item = index[i];
                if (item.name.toLowerCase().indexOf(lq) !== -1) {
                    html += '<div class="search-result">' +
                        '<a href="' + item.viewUrl + '">' + item.name + '</a>' +
                        '<div><span class="lang">' + item.lang + '</span> &middot; <span class="cat">' + item.category + '</span></div>' +
                        '</div>';
                    count++;
                    if (count >= 50) break;
                }
            }
            if (count === 0) {
                html = '<p style="color:#888;text-align:center;">No results found.</p>';
            }
            results.innerHTML = html;
        }
    })();
    </script>
</body>
</html>"""
    return search_html


def generate_search_index(languages_data):
    """Generate search-index.json from all languages and categories."""
    index = []
    for lang, categories in languages_data:
        for cat_name, idmnd_files in categories:
            for f in idmnd_files:
                name = f.stem
                view_url = f"/{lang}/view.html?l={url_quote(lang)}&c={url_quote(cat_name)}&set={url_quote(name)}"
                index.append({
                    "name": name,
                    "lang": lang.capitalize(),
                    "category": cat_name.replace("-", " ").title(),
                    "viewUrl": view_url,
                })
    return json.dumps(index, ensure_ascii=False, indent=2)


def generate_news_index():
    """Generate news/index.html as a static redirect to page1.html."""
    return """<!DOCTYPE html>
<html>
<head>
   <meta charset="UTF-8">
 <meta charset="utf-8">
    <title>News</title>
    <meta http-equiv="refresh" content="0;url=page1.html">
    <script>window.location.href='page1.html';</script>
</head>
<body>
    <p>Redirecting to <a href="page1.html">News</a>...</p>
</body>
</html>"""


def patch_view_js():
    """Keep quiz buttons labeled No/OK; numeric scores remain in the top counters."""
    js_path = PUBLIC_DIR / "js" / "view.js"
    if not js_path.is_file():
        return

    content = js_path.read_text(encoding="utf-8")
    original = content

    # Modern view.js
    content = content.replace(
        "rightBtn.setAttribute('value', scoreOk);",
        "rightBtn.setAttribute('value', 'OK');"
    )
    content = content.replace(
        "wrongBtn.setAttribute('value', scoreNo);",
        "wrongBtn.setAttribute('value', 'No');"
    )

    # Legacy view.js
    content = content.replace(
        'document.getElementById("Right").setAttribute("value", scoreOk);',
        'document.getElementById("Right").setAttribute("value", "OK");'
    )
    content = content.replace(
        'document.getElementById("Wrong").setAttribute("value", scoreNo);',
        'document.getElementById("Wrong").setAttribute("value", "No");'
    )

    # Reset after a completed round.
    content = content.replace(
        'rightBtn.setAttribute("value", "0");',
        'rightBtn.setAttribute("value", "OK");'
    )
    content = content.replace(
        'wrongBtn.setAttribute("value", "0");',
        'wrongBtn.setAttribute("value", "No");'
    )
    content = content.replace(
        'document.getElementById("Right").setAttribute("value", "0");',
        'document.getElementById("Right").setAttribute("value", "OK");'
    )
    content = content.replace(
        'document.getElementById("Wrong").setAttribute("value", "0");',
        'document.getElementById("Wrong").setAttribute("value", "No");'
    )

    if content != original:
        js_path.write_text(content, encoding="utf-8")
        print("  Patched js/view.js: quiz buttons remain No / OK")


def _markdown_inline(text):
    """Render the small Markdown inline syntax used by the editorial pages."""
    # Preserve raw HTML while escaping actual Markdown text.
    tokens = []

    def hold(value):
        token = f"\x00HTML{len(tokens)}\x00"
        tokens.append(value)
        return token

    # Images and links are Markdown syntax, so process them before HTML tags.
    def image_repl(m):
        alt = html.escape(m.group(1), quote=True)
        src = html.escape(m.group(2), quote=True)
        return hold(f'<img src="{src}" alt="{alt}">')

    def link_repl(m):
        label = _markdown_inline(m.group(1))
        href = html.escape(m.group(2), quote=True)
        return hold(f'<a href="{href}">{label}</a>')

    text = re.sub(r'!\[([^]]*)\]\(([^)]+)\)', image_repl, text)
    text = re.sub(r'\[([^]]+)\]\(([^)]+)\)', link_repl, text)

    parts = re.split(r'(<[^>]+>)', text)
    out = []
    for part in parts:
        if part.startswith('<') and part.endswith('>'):
            out.append(hold(part))
        else:
            value = html.escape(part, quote=False)
            value = re.sub(r'`([^`]+)`', r'<code>\1</code>', value)
            value = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', value)
            value = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', value)
            value = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', value)
            value = re.sub(r'(?<!_)_([^_]+)_(?!_)', r'<em>\1</em>', value)
            out.append(value)

    result = ''.join(out)
    for i, value in enumerate(tokens):
        result = result.replace(f"\x00HTML{i}\x00", value)
    return result


def _is_table_separator(line):
    cells = [c.strip() for c in line.strip().strip('|').split('|')]
    return bool(cells) and all(re.fullmatch(r':?-{3,}:?', c) for c in cells)


def render_markdown(markdown_text):
    """Render the editorial Markdown used by Idiomind without external packages.

    This intentionally implements the Markdown subset used by the site's content:
    headings, paragraphs, emphasis, inline code, links, images, ordered/unordered
    lists, tables, indented code blocks, horizontal rules, and raw HTML.
    """
    lines = markdown_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out = []
    i = 0
    paragraph = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            text = ' '.join(x.strip() for x in paragraph).strip()
            if text:
                out.append(f'<p>{_markdown_inline(text)}</p>')
            paragraph = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        # Preserve raw HTML lines exactly. Markdown is still processed on the
        # surrounding lines, so HTML can be used for layout-specific elements.
        if stripped.startswith('<') and stripped.endswith('>'):
            flush_paragraph()
            out.append(line)
            i += 1
            continue

        # Indented code block (used by the installation commands and diagrams).
        if line.startswith('    ') or line.startswith('\t'):
            flush_paragraph()
            code = []
            while i < len(lines):
                current = lines[i]
                if current.startswith('    '):
                    code.append(current[4:])
                    i += 1
                elif current.startswith('\t'):
                    code.append(current[1:])
                    i += 1
                elif not current.strip():
                    code.append('')
                    i += 1
                else:
                    break
            while code and code[-1] == '':
                code.pop()
            out.append('<pre><code>' + html.escape('\n'.join(code), quote=False) + '</code></pre>')
            continue

        # ATX headings.
        heading = re.match(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            out.append(f'<h{level}>{_markdown_inline(heading.group(2))}</h{level}>')
            i += 1
            continue

        # Horizontal rule.
        if re.fullmatch(r'\s{0,3}((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})', line):
            flush_paragraph()
            out.append('<hr>')
            i += 1
            continue

        # GFM-style table.
        if i + 1 < len(lines) and '|' in line and _is_table_separator(lines[i + 1]):
            flush_paragraph()
            headers = [c.strip() for c in line.strip().strip('|').split('|')]
            i += 2
            rows = []
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            out.append('<table>')
            out.append('<thead><tr>' + ''.join(f'<th>{_markdown_inline(c)}</th>' for c in headers) + '</tr></thead>')
            out.append('<tbody>')
            for row in rows:
                cells = row + [''] * max(0, len(headers) - len(row))
                out.append('<tr>' + ''.join(f'<td>{_markdown_inline(c)}</td>' for c in cells[:len(headers)]) + '</tr>')
            out.append('</tbody></table>')
            continue

        # Unordered list.
        if re.match(r'^\s{0,3}[-+*]\s+', line):
            flush_paragraph()
            items = []
            while i < len(lines):
                m = re.match(r'^\s{0,3}[-+*]\s+(.+)$', lines[i])
                if not m:
                    break
                items.append(m.group(1).strip())
                i += 1
            out.append('<ul>' + ''.join(f'<li>{_markdown_inline(x)}</li>' for x in items) + '</ul>')
            continue

        # Ordered list.
        if re.match(r'^\s{0,3}\d+[.)]\s+', line):
            flush_paragraph()
            items = []
            while i < len(lines):
                m = re.match(r'^\s{0,3}\d+[.)]\s+(.+)$', lines[i])
                if not m:
                    break
                items.append(m.group(1).strip())
                i += 1
            out.append('<ol>' + ''.join(f'<li>{_markdown_inline(x)}</li>' for x in items) + '</ol>')
            continue

        # Normal Markdown paragraph line.
        paragraph.append(line)
        i += 1

    flush_paragraph()
    return '\n'.join(out)


def render_static_markdown_page(relative_html):
    """Render one HTML template by injecting only its Markdown content."""
    template_path = SOURCE_DIR / relative_html
    content_rel = MARKDOWN_CONTENT[relative_html]
    content_path = SOURCE_DIR / content_rel

    if not template_path.is_file():
        raise RuntimeError(f"HTML template not found: {template_path}")
    if not content_path.is_file():
        raise RuntimeError(f"Markdown content not found: {content_path}")

    template = template_path.read_text(encoding="utf-8", errors="replace")
    markdown_text = content_path.read_text(encoding="utf-8", errors="replace")
    if "{{CONTENT}}" not in template:
        raise RuntimeError(
            f"HTML template has no {{CONTENT}} placeholder: {template_path}"
        )

    content_html = render_markdown(markdown_text).strip()
    return template.replace("{{CONTENT}}", content_html, 1)


def write_markdown_page(relative_html):
    """Build one Markdown-backed static page into public/."""
    output_path = PUBLIC_DIR / relative_html
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_static_markdown_page(relative_html),
        encoding="utf-8",
    )
    print(f"  Generated {relative_html} from Markdown")


def copy_static_files():
    """Copy static files from SourceSite to public."""
    dist = PUBLIC_DIR

    # CSS
    src = SOURCE_DIR / "css"
    if src.is_dir():
        shutil.copytree(src, dist / "css", dirs_exist_ok=True)

    # JS
    src = SOURCE_DIR / "js"
    if src.is_dir():
        shutil.copytree(src, dist / "js", dirs_exist_ok=True)

    # Images
    src = SOURCE_DIR / "images"
    if src.is_dir():
        shutil.copytree(src, dist / "images", dirs_exist_ok=True)

    # Share (may contain symlinks to external dirs)
    src = SOURCE_DIR / "share"
    if src.is_dir():
        dst_share = dist / "share"
        dst_share.mkdir(exist_ok=True)
        for entry in src.iterdir():
            if entry.is_symlink():
                target = entry.resolve()
                dst_link = dst_share / entry.name
                if target.is_dir():
                    shutil.copytree(target, dst_link, dirs_exist_ok=True, follow_symlinks=True)
                elif target.is_file():
                    shutil.copy2(target, dst_link)
            elif entry.is_dir():
                shutil.copytree(entry, dst_share / entry.name, dirs_exist_ok=True)
            else:
                shutil.copy2(entry, dst_share / entry.name)

    # Files
    src = SOURCE_DIR / "Files"
    if src.is_dir():
        shutil.copytree(src, dist / "Files", dirs_exist_ok=True)

    # Static HTML pages. Markdown-backed pages are rendered from their
    # templates below; the remaining pages continue to be copied unchanged.
    for fname in STATIC_HTML:
        if fname in MARKDOWN_CONTENT:
            continue
        src = SOURCE_DIR / fname
        if src.is_dir():
            shutil.copytree(src, dist / fname, dirs_exist_ok=True)
        elif src.is_file():
            shutil.copy2(src, dist / fname)

    # Favicons
    for fname in ["favicon.ico", "favicon-16x16.png", "favicon-32x32.png", "favicon32.ico"]:
        src = SOURCE_DIR / fname
        if src.is_file():
            shutil.copy2(src, dist / fname)

    # Root images (dona.png, donat.png, done.png)
    for fname in ["dona.png", "donat.png", "done.png"]:
        src = SOURCE_DIR / fname
        if src.is_file():
            shutil.copy2(src, dist / fname)

    # News pages
    news_dist = dist / "news"
    news_dist.mkdir(exist_ok=True)
    for fname in ["page1.html", "page2.html"]:
        relative = f"news/{fname}"
        if relative in MARKDOWN_CONTENT:
            continue
        src = SOURCE_DIR / "news" / fname
        if src.is_file():
            shutil.copy2(src, news_dist / fname)


def copy_idmnd_files(lang, lang_dir, dist_lang):
    """Sync .idmnd files from the external master repository."""
    for f in lang_dir.rglob("*.idmnd"):
        rel = f.relative_to(lang_dir)
        dest = dist_lang / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        # .idmnd packages can be large (audio/images). Avoid copying them
        # on every build when the destination already contains the same file.
        if dest.is_file():
            src_stat = f.stat()
            dst_stat = dest.stat()
            if src_stat.st_size == dst_stat.st_size and src_stat.st_mtime_ns <= dst_stat.st_mtime_ns:
                continue

        print(f"    Syncing {rel}")
        shutil.copy2(f, dest)


def clean_public_preserving_idmnd():
    """Clean generated site files in public/ while preserving packaged .idmnd files.

    The modern .idmnd files are deployment assets containing their own audio,
    images, etc. They must survive a rebuild of the static HTML site.
    """
    if not PUBLIC_DIR.exists():
        PUBLIC_DIR.mkdir(parents=True)
        return

    # Delete every file except .idmnd packages.
    for path in sorted(PUBLIC_DIR.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_file() and path.suffix.lower() != ".idmnd":
            path.unlink()

    # Remove empty directories, but keep directories that contain .idmnd files.
    for path in sorted(PUBLIC_DIR.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                # Directory is non-empty (typically because it contains .idmnd).
                pass


def generate_doc_pages():
    """Generate the doc/ pages (doc/index.html + doc/feedback/)."""

    # --- doc/index.html ---
    # Based on doc/index.php but static: strip PHP,
    # remove dead rss_releases include, rewrite .php links.
    doc_src = SOURCE_DIR / "doc" / "index.php"
    if doc_src.is_file():
        content = doc_src.read_text(encoding="utf-8", errors="replace")

        # Remove any PHP blocks (legacy PHP + rss_releases include)
        content = re.sub(r"<\?php.*?\?>", "", content, flags=re.S)

        # Fix class="current_category" anchor to index.html
        content = content.replace('href="index.php"', 'href="index.html"')

        # These pages live at the site root, not under /doc/. Fix relative refs.
        for name in ["help.html", "library.html"]:
            content = content.replace(f'href="{name}"', f'href="/{name}"')
        for name in ["favicon-32x32.png", "favicon-16x16.png", "favicon.ico"]:
            content = content.replace(f'href="{name}"', f'href="/{name}"')
            content = content.replace(f'src="{name}"', f'src="/{name}"')

        # Fix /news?page=1 -> /news/index.html (news redirect)
        content = content.replace('href="/news?page=1"', 'href="/news/index.html"')
        content = content.replace('href="/news?page=1">', 'href="/news/index.html">')


        doc_dist = PUBLIC_DIR / "doc"
        doc_dist.mkdir(parents=True, exist_ok=True)
        (doc_dist / "index.html").write_text(content, encoding="utf-8")
        print("  Generated doc/index.html")

    # --- doc/feedback/index.html + rss.xml ---
    # rg_NOTE: original is an RSS generator over .txt feedback files.
    # We generate a static rss.xml at build time and a simple index.html viewer.
    fb_dir = SOURCE_DIR / "doc" / "feedback"
    if fb_dir.is_dir():
        fb_dist = PUBLIC_DIR / "doc" / "feedback"
        fb_dist.mkdir(parents=True, exist_ok=True)

        # Collect .txt feedback files, sorted by mtime (newest first)
        from pathlib import Path as _P
        txt_files = []
        for f in fb_dir.glob("*.txt"):
            txt_files.append((f, f.stat().st_mtime))
        txt_files.sort(key=lambda x: -x[1])

        items = []
        for f, mtime in txt_files:
            name = f.stem
            # strip " .txt" mid-filename spacing
            try:
                raw = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                raw = ""
            desc = raw.strip()
            items.append((name, mtime, desc))

        # Build RSS XML
        from datetime import datetime as _D
        rss_items = []
        for name, mtime, desc in items:
            dt = _D.utcfromtimestamp(mtime)
            pub = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
            rss_items.append(f"""<item>
<title>{esc(name)}</title>
<pubDate>{pub}</pubDate>
<description>{esc(desc)}</description>
</item>""")
        rss_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<atom:link href="https://idiomind.sourceforge.io/doc/feedback/rss.xml" rel="self" type="application/rss+xml"/>
<title>Feedback - Idiomind</title>
<link>https://idiomind.sourceforge.io/doc/feedback/</link>
<description>Latest Published</description>
<language>en-us</language>
<generator>Idiomind Build</generator>
{chr(10).join(rss_items)}
</channel>
</rss>"""
        (fb_dist / "rss.xml").write_text(rss_xml, encoding="utf-8")

        # Simple index.html viewer listing feedback with RSS link
        fb_rows = []
        for i, (name, mtime, desc) in enumerate(items):
            fb_rows.append(f"""<li>
<h3>{esc(name)}</h3>
<p>{esc(desc)}</p>
</li>""")
        fb_list = chr(10).join(fb_rows) if fb_rows else "<li>No feedback yet.</li>"
        fb_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">

<meta charset="utf-8">
<title>Feedback - Idiomind</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="/css/classic.css">
<link rel="stylesheet" href="/css/fonts.css">
<link rel="shortcut icon" href="/favicon.ico?v=2" type="image/x-icon">
</head>
<body>
<div class="wrapper">
<div class="logo_bar">
<h1>Idiomind</h1>
<p>Feedback from users</p>
</div>
<div class="content_wrapper">
<div class="content">
<p><a href="/doc/feedback/rss.xml">Subscribe via RSS</a></p>
<ul>{fb_list}</ul>
</div>
</div>
</div>
<div class="footer">
<span><p><small>&copy; 2026 <a href="https://idiomind.sourceforge.io">Idiomind Project</a></small></p></span>
</div>
</body>
</html>"""
        (fb_dist / "index.html").write_text(fb_html, encoding="utf-8")
        print(f"  Generated doc/feedback/index.html + rss.xml ({len(items)} feedback items)")


def fix_php_references():
    """Fix .php references in copied static HTML files in public/."""
    import re

    # Mapping of .php references to their static equivalents
    replacements = [
        # Root pages
        (r'href="index\.php"', 'href="index.html"'),
        (r"href='index\.php'", "href='index.html'"),
        (r'href="/index\.php"', 'href="/index.html"'),
        (r'href="\.\./index\.php"', 'href="../index.html"'),
        (r'href="\.\./\.\./index\.php"', 'href="../../index.html"'),
        (r'action="/sub\.php"', 'action="https://forms.gle/REPLACE_WITH_REAL_FORM"'),
    ]

    for html_file in PUBLIC_DIR.rglob("*.html"):
        try:
            content = html_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        original = content
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        if content != original:
            html_file.write_text(content, encoding="utf-8")
            rel = html_file.relative_to(PUBLIC_DIR)
            print(f"  Fixed .php refs in: {rel}")


def fix_broken_refs():
    """Fix broken references in generated/copy static HTML files."""
    import re

    # JS mobile detection snippet (matches original PHP logic)
    mobile_js = """
    <script>
    (function(){
        var ua = navigator.userAgent;
        if (/Windows Phone|iPhone|Android/i.test(ua)) {
            window.location.href = '/mobile.html';
        }
    })();
    </script>
"""

    for html_file in PUBLIC_DIR.rglob("*.html"):
        try:
            content = html_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        original = content

        # Fix ./css/css -> /css/ (bug in original mobile templates)
        content = content.replace('href="./css/css"', 'href="/css/classic.css"')

        # Fix relative favicon paths in news/ pages
        rel_path = html_file.relative_to(PUBLIC_DIR)
        if str(rel_path).startswith("news/"):
            content = content.replace('href="favicon-32x32.png"', 'href="/favicon-32x32.png"')
            content = content.replace('href="favicon-16x16.png"', 'href="/favicon-16x16.png"')
            content = content.replace('href="favicon.ico"', 'href="/favicon.ico"')
            content = content.replace("href='favicon.ico'", "href='/favicon.ico'")
            content = content.replace('href="favicon.ico?v=2"', 'href="/favicon.ico?v=2"')

        # Fix fancybox v1 refs -> v2 in legacy copied templates
        content = content.replace('/js/fancybox/jquery.fancybox-1.3.4.pack.js', '/js/fancybox/jquery.fancybox.js')
        content = content.replace('/js/fancybox/jquery.fancybox-1.3.4.css', '/js/fancybox/jquery.fancybox.css')

        # Fix box.html?lang=...&category=... -> category/index.html
        # Pattern: /{lang}/box.html?lang={lang}&category={cat}
        def fix_box_link(m):
            lang_part = m.group(1)
            cat_part = m.group(2)
            from urllib.parse import unquote
            cat_decoded = unquote(cat_part)
            return f'/{lang_part}/{cat_decoded}/index.html'

        content = re.sub(
            r'/([\w]+)/box\.html\?lang=[^"&]+&category=([^"&]+)',
            fix_box_link,
            content
        )
        if content != original:
            html_file.write_text(content, encoding="utf-8")
            rel = html_file.relative_to(PUBLIC_DIR)
            print(f"  Fixed broken refs in: {rel}")


def build():
    """Main build function."""
    print("=" * 60)
    print("  Idiomind Static Site Builder")
    print("=" * 60)

    # Validate the source tree before touching the target.
    if not SOURCE_DIR.is_dir():
        raise RuntimeError(f"SourceSite directory not found: {SOURCE_DIR}")
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    # Clean generated site files, but preserve modern .idmnd packages.
    # These packages contain their own audio/images and can total hundreds
    # of megabytes, so the build must not delete or recopy them unnecessarily.
    print(f"Cleaning generated site files in {PUBLIC_DIR} (preserving .idmnd)...")
    clean_public_preserving_idmnd()

    # The .idmnd master repository lives outside the project/home partition.
    # Fail explicitly if it is not mounted; otherwise a missing mount could make
    # the build silently generate a site with zero topics.
    if not IDMND_SOURCE.is_dir():
        raise RuntimeError(f"IDMND source repository not found or not mounted: {IDMND_SOURCE}")

    # Discover languages from the external .idmnd repository.
    languages = find_languages()
    print(f"\nLanguages found: {', '.join(languages)}")

    # Store data for search index generation
    languages_data = []

    # Copy static files
    print("\nCopying static files...")
    copy_static_files()
    patch_view_js()

    # Render Markdown-backed editorial pages.
    # The HTML files remain templates; only {{CONTENT}} is replaced.
    for relative_html in MARKDOWN_CONTENT:
        if relative_html == "index.html":
            print("Generating index.html from Markdown...")
        write_markdown_page(relative_html)

    # Generate news redirect
    print("Generating news/index.html...")
    (PUBLIC_DIR / "news" / "index.html").write_text(generate_news_index(), encoding="utf-8")

    # Generate search
    print("Generating search.html...")
    (PUBLIC_DIR / "search.html").write_text(generate_search(), encoding="utf-8")

    # Generate per-language content
    for lang in languages:
        lang_dir = IDMND_SOURCE / lang
        dist_lang = PUBLIC_DIR / lang
        dist_lang.mkdir(parents=True, exist_ok=True)

        categories = find_categories(lang_dir)
        languages_data.append((lang, categories))

        cat_count = len(categories)
        file_count = sum(len(files) for _, files in categories)
        print(f"\n--- {lang} ({cat_count} categories, {file_count} .idmnd files) ---")

        # Generate home pages
        print(f"  Generating {lang}/index.html...")
        (dist_lang / "index.html").write_text(generate_lang_index(lang, categories), encoding="utf-8")

        # Generate view pages (same for all categories)
        print(f"  Generating {lang}/view.html...")
        (dist_lang / "view.html").write_text(generate_view(lang), encoding="utf-8")

        # Generate favs pages
        print(f"  Generating {lang}/favs.html...")
        (dist_lang / "favs.html").write_text(generate_favs(lang), encoding="utf-8")

        # Generate RSS
        print(f"  Generating {lang}/rss.xml...")
        (dist_lang / "rss.xml").write_text(generate_rss_xml(lang, categories), encoding="utf-8")

        # Generate per-category pages
        for cat_name, idmnd_files in categories:
            cat_dir = dist_lang / cat_name
            cat_dir.mkdir(parents=True, exist_ok=True)

            print(f"  Generating {lang}/{cat_name}/index.html ({len(idmnd_files)} topics)...")
            (cat_dir / "index.html").write_text(generate_box(lang, cat_name, idmnd_files), encoding="utf-8")

        # Copy .idmnd files
        print(f"  Copying .idmnd files...")
        copy_idmnd_files(lang, lang_dir, dist_lang)

    # Generate the root library page (language picker + topic grid by cookie)
    print("\nGenerating library.html...")
    (PUBLIC_DIR / "library.html").write_text(generate_library_page(languages_data), encoding="utf-8")

    # Generate search index
    print("\nGenerating search-index.json...")
    (PUBLIC_DIR / "search-index.json").write_text(generate_search_index(languages_data), encoding="utf-8")

    # Generate global RSS
    print("Generating global rss.xml...")
    all_cats = []
    for lang in languages:
        lang_dir = IDMND_SOURCE / lang
        all_cats.extend(find_categories(lang_dir))
    (PUBLIC_DIR / "rss.xml").write_text(generate_rss_xml("_global_", all_cats), encoding="utf-8")

    # Post-process: fix .php references in copied static HTML files
    print("\nPost-processing: fixing references in static HTML files...")
    fix_php_references()
    fix_broken_refs()

    # library.html is generated from the current .idmnd repository.
    # It is intentionally NOT copied back into SourceSite: SourceSite is the source,
    # public/ is the build target.

    # Generate doc/ pages (not part of language tree)
    print("\nGenerating doc pages...")
    generate_doc_pages()

    # Summary
    total_files = sum(1 for _ in PUBLIC_DIR.rglob("*") if _.is_file())
    print(f"\n{'=' * 60}")
    print(f"  Build complete!")
    print(f"  Target: {PUBLIC_DIR}")
    print(f"  Total files: {total_files}")
    print(f"{'=' * 60}")

    # Offer to start Apache only when the service is not already running.
    # If Apache is active, leave it untouched and finish silently.
    import shutil
    import subprocess

    apache_running = False
    if shutil.which("systemctl") is not None:
        status = subprocess.run(
            ["systemctl", "is-active", "--quiet", "apache2"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        apache_running = status.returncode == 0

    if apache_running:
        print("  Apache is already running.")
    else:
        try:
            answer = input("\n  Apache is not running. Start Apache? [y/N]: ").strip()
        except (EOFError, KeyboardInterrupt):
            answer = ""
            print()

        if answer.lower() == "y":
            if shutil.which("sudo") is None:
                print("  ERROR: 'sudo' was not found; Apache was not started.")
            elif shutil.which("systemctl") is None:
                print("  ERROR: 'systemctl' was not found; Apache was not started.")
            else:
                print("  Starting Apache...")
                result = subprocess.run(["sudo", "systemctl", "start", "apache2"])
                if result.returncode == 0:
                    print("  Apache started.")
                else:
                    print(f"  Apache was not started (exit code {result.returncode}).")


if __name__ == "__main__":
    build()
