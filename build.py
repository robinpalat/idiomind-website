#!/usr/bin/env python3
"""
build.py - Generador del sitio estatico de Idiomind

Genera un directorio dist/ con todo lo necesario para servir en SourceForge
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
DIST_DIR = BASE_DIR / "dist"

LANGUAGES = []

SKIP_DIRS = {
    ".git", "community", "doc", "tmp", "dist", "build",
    "css", "js", "images", "share", "Files", "news",
}

SKIP_FILES_ROOT = {
    "index.php", "home.php", "mobile.php", "mobilehome.php",
    "apphome.php", "box.php", "mobilebox.php", "appbox.php",
    "view.php", "mobileview.php", "appview.php",
    "search.php", "rss.php", "fetchfeed.php", "listen.php",
    "download.php", "upload.php", "sub.php",
    "favs.php", "mobilefavs.php", "json.php",
    "analyticstracking.php",
    ".htaccess", ".user.ini", "php.ini", "build.py",
}

STATIC_HTML = [
    "help.html", "helpm.html",
    "library.html", "librarym.html",
    "contact.html", "contactm.html",
    "donate.html", "donatem.html",
    "maintenance.html", "privacypolicy.htm",
]

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
    for entry in sorted(BASE_DIR.iterdir()):
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
        html_parts.append(f"""<div class="feed-title"><a data-fancybox data-type="iframe" class="btn btn-primary" data-small-btn="true" href="{view_link}">{esc(name)}</a></div> <small><font color="#1FAF12">Published </font><font color="#626262">{date_str}</font></small> <br><br>""")

    return "\n".join(html_parts)


def generate_category_item(lang, cat_name, count, endpoint, cls="category-item", attrs=""):
    """Build the clickable category component: name + topics count + folder icon.

    El ancla conserva `data-fancybox`/`href` para abrir exactamente el mismo
    lightbox de siempre. El enlace box.html|mobilebox.html|appbox.html es
    reescrito a <lang>/<category>/index.html por el post-procesado.
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
                    <a class="site-nav-link" href="/contact.html" onfocus="this.blur();">Contact</a>
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


def generate_library_page(languages_data):
    """Generate the root library.html (selector de idioma + grilla de topics).

    - Si NO hay cookie `language`: se muestra la presentación que invita a
      elegir el idioma que se está aprendiendo.
    - Al elegir un idioma se guarda la cookie `language` (idioma target) y la
      grilla de contenidos de ese idioma se presenta en esta misma página,
      abriendo los topics con el mismo lightbox de siempre.
    - La siguiente visita a la pestaña Library entra directamente en la
      grilla del idioma guardado.
    """
    picker_items = []
    lang_sections = []
    lang_js = []
    for lang, categories in languages_data:
        uplang = lang.capitalize()
        cat_items = []
        total = 0
        for cat_name, idmnd_files in categories:
            count = len(idmnd_files)
            total += count
            if count > 0:
                cat_items.append(generate_category_item(
                    lang, cat_name, count, "box.html",
                    attrs='data-fancybox data-type="iframe" data-small-btn="true"'))
        cat_html = "\n".join(cat_items)
        latest = generate_latest_html(lang, categories).replace(' class="btn btn-primary"', '')
        word = "topic" if total == 1 else "topics"
        lang_js.append(f'"{lang}"')
        picker_items.append(f"""<li>
                    <a class="language-option" data-lang="{lang}" href="/{lang}/" onclick="return libPick('{lang}');">
                        <span class="language-name">{esc(uplang)}</span>
                        <span class="language-count">{total} {word}</span>
                        <i class="fa fa-language language-icon" aria-hidden="true"></i>
                    </a>
                </li>""")
        lang_sections.append(f"""<section class="library-topic-view" data-lang="{lang}" hidden>
                    <header class="library-head">
                        <p class="page-kicker">Topic library</p>
                        <h1 class="page-title">{esc(uplang)}</h1>
                        <p class="library-switch"><a href="#" onclick="return libPick('');">Change language</a></p>
                    </header>
                    <table width='100%'>
                        <tr>
                            <td valign="top">
                                <div class="feed-lists">
                                    <h1><i class="fa fa-bolt" aria-hidden="true"></i> Latest published</h1>
{latest}
                                </div>
                            </td>
                            <td valign="top">
                                <div class="fav-lists" id="favlists-{lang}"></div>
                            </td>
                        </tr>
                    </table>
                    <div class="category-grid">
{cat_html}
                    </div>
                </section>""")

    picker_html = "\n".join(picker_items)
    sections_html = "\n".join(lang_sections)
    langs_js = ",".join(lang_js)

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head><meta http-equiv="Content-Type" content="text/html; charset=windows-1252">
    <meta charset="utf-8">
    <title>Idiomind | Library</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="keywords" content="learn english free, learn english online, learn english grammar, learn english vocabulary, free English lessons, english vocabulary, idiom library, ESL, EFL, pronunciation, grammar, vocabulary, tests, lessons, quiz, resources"/>
    <meta name="description" content="Idiomind is a valuable tool for language learners seeking to enhance their language skills. Choose the language you are learning and explore the topics shared by the community."/>

    <link rel="stylesheet" type="text/css" href="/css/classic.css">
    <link rel="stylesheet" type="text/css" href="/css/fonts.css">
    <link href="/css/fa/css/font-awesome.css" rel="stylesheet" type="text/css" />
    <link rel="stylesheet" type="text/css" href="/js/fancybox/jquery.fancybox.css" media="screen" />

    <style>
    /* Mismo tamaño de lightbox que en las páginas de idioma */
    .fancybox-slide--iframe .fancybox-content {{
        width: 74%;
        height: 86%;
        max-width: 1120px;
        max-height: 96%;
        margin: 0;
        background: var(--surface);
        border-radius: var(--radius-md);
        overflow: hidden;
        box-shadow: 0 30px 70px rgba(35, 27, 18, 0.28);
    }}
    @media (max-width: 900px) {{
        .fancybox-slide--iframe .fancybox-content {{
            width: 92%;
            height: 88%;
            max-width: 100%;
        }}
    }}
    </style>

    <link rel="shortcut icon" href="/favicon.ico?v=2" type="image/x-icon">
    <link rel="icon" type="image/png" href="favicon-32x32.png" sizes="32x32"/>
    <link rel="icon" type="image/png" href="favicon-16x16.png" sizes="16x16"/>
    <link rel="image_src" href="/images/logo.png"/><!--formatted-->

    <script type="text/javascript">
        /* Idioma target de aprendizaje, guardado en la cookie "language"
           (la misma cookie que establecen las páginas de cada idioma). */
        var LIB_COOKIE = 'language';
        var LIB_LANGS = [{langs_js}];
        function libGetCookie() {{
            var name = LIB_COOKIE + '=';
            var ca = document.cookie.split(';');
            for (var i = 0; i < ca.length; i++) {{
                var c = ca[i];
                while (c.charAt(0) == ' ') c = c.substring(1);
                if (c.indexOf(name) == 0) {{
                    try {{ return decodeURIComponent(c.substring(name.length, c.length)); }}
                    catch (e) {{ return c.substring(name.length, c.length); }}
                }}
            }}
            return '';
        }}
        function libSetCookie(value) {{
            var d = new Date();
            d.setTime(d.getTime() + (365 * 24 * 60 * 60 * 1000));
            document.cookie = LIB_COOKIE + '=' + encodeURIComponent(value) + '; expires=' + d.toUTCString() + '; path=/; SameSite=Lax';
        }}
        function libGetCookieValue(name) {{
            var n = name + '=';
            var ca = document.cookie.split(';');
            for (var i = 0; i < ca.length; i++) {{
                var c = ca[i];
                while (c.charAt(0) == ' ') c = c.substring(1);
                if (c.indexOf(n) == 0) {{
                    try {{ return decodeURIComponent(c.substring(n.length, c.length)); }}
                    catch (e) {{ return c.substring(n.length, c.length); }}
                }}
            }}
            return '';
        }}
        function libShowView(lang) {{
            var views = document.getElementsByClassName('library-topic-view');
            var found = false;
            for (var i = 0; i < views.length; i++) {{
                var on = views[i].getAttribute('data-lang') === lang;
                views[i].hidden = !on;
                if (on) found = true;
            }}
            var picker = document.getElementById('library-picker');
            if (picker) picker.hidden = (lang && found);
            libShowPinned(lang);
        }}
        function libListFavs(lang) {{
            var faves = libGetCookieValue(lang.charAt(0) + 'PINS');
            if (!faves) return;
            faves = faves.split('|');
            var div = document.getElementById('favlists-' + lang);
            if (!div || faves.length < 1) return;
            var out = '<h1>Pinned <i class="fa fa-thumb-tack" aria-hidden="true"></i></h1>';
            for (var i = 0; i < faves.length; i++) {{
                var fav = faves[i];
                if (!fav) continue;
                out += '<a data-fancybox data-type="iframe" data-small-btn="true" '
                    + 'href="/' + lang + '/view.html?l=' + lang + '&c=fav&set=' + fav + '">'
                    + fav + '</a><br>';
            }}
            div.innerHTML = out;
        }}
        function libShowPinned(lang) {{
            var views = document.getElementsByClassName('library-topic-view');
            for (var i = 0; i < views.length; i++) {{
                var l = views[i].getAttribute('data-lang');
                if (l && l !== lang) {{
                    var d = document.getElementById('favlists-' + l);
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
        (function() {{
            var saved = libGetCookie();
            if (saved) {{
                var known = false;
                for (var i = 0; i < LIB_LANGS.length; i++) {{ if (LIB_LANGS[i] === saved) known = true; }}
                if (known) libShowView(saved);
            }}
        }})();
    </script>

    <script src="//code.jquery.com/jquery-3.2.1.min.js"></script>
    <script type="text/javascript" src="/js/fancybox/jquery.fancybox.js"></script>

    {GA_SNIPPET}
</head>

<body>

    <div class="library-main">

        <header class="site-header">
            <div class="brand">
                <img class="brand-mark" src="/images/logo.png" alt="Idiomind logo">
                <a class="brand-wordmark" href="/index.html">Idiomind</a>
            </div>
            <nav class="site-nav" aria-label="Main navigation">
                <a class="site-nav-link" href="index.html" onfocus="this.blur();">Introduction</a>
                <a class="site-nav-link" href="help.html" onfocus="this.blur();">Getting started</a>
                <a class="site-nav-link current" href="library.html" onfocus="this.blur();">Library</a>
                <a class="site-nav-link" href="/news/index.html" onfocus="this.blur();">News</a>
                <a class="site-nav-link" href="contact.html" onfocus="this.blur();">Contact</a>
            </nav>
            <a class="site-donate" href="/donate.html">Donate</a>
        </header>

        <section id="library-picker" class="language-picker">
            <header class="library-head">
                <p class="page-kicker">Idiomind library</p>
                <h1 class="page-title">Choose the language you are learning</h1>
                <p class="page-lead">Select the language you are learning to browse the topics shared by the community. Your choice is remembered on this device.</p>
            </header>
            <ul class="language-list">
{picker_html}
            </ul>
        </section>

{sections_html}

        <footer class="site-footer">
            <p>&copy; 2022 <a href="https://idiomind.sourceforge.io">Idiomind Project</a></p>
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
        <div> &copy 2015-2023 <a href="https://idiomind.sourceforge.io">idiomind</a> Project | <a href="http://idiomind.sourceforge.io/contact.html">Contact</a> | <a href="../privacypolicy.htm">Privacy</a><br><a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">All the content is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike</a>.
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


def generate_lang_mobile(lang, categories):
    """Generate the mobile home page for a language."""
    uplang = lang.capitalize()
    cat_boxes = []
    for cat_name, idmnd_files in categories:
        count = len(idmnd_files)
        if count > 0:
            cat_boxes.append(generate_category_item(
                lang, cat_name, count, "mobilebox.html",
                attrs='data-fancybox data-type="iframe"'))

    categories_html = "\n".join(cat_boxes)
    latest = generate_latest_html(lang, categories)

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"/>

<head>
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
    <link href="/css/mobilehome.css" rel="stylesheet" type="text/css" />
    <link href="/css/fa/css/font-awesome.css" rel="stylesheet" type="text/css" />
    <link rel="stylesheet" type="text/css" href="/js/fancybox/jquery.fancybox.css" media="screen" />

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
                div.innerHTML = "<h1 style='text-align:left'><i class='fa fa-thumb-tack' aria-hidden='true'></i> Pinned</h1>";
                for (fav of faves) {{
                    div.innerHTML = div.innerHTML + '<a data-fancybox data-type="iframe" class="btn btn-primary"  data-small-btn="true" href="/{esc(lang)}/mobileview.html?l={esc(lang)}&c=fav&set='+fav+'">'+fav+'</a><br><br>';
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
                        <div class="fav-lists" id="favlists"></div>
                        <div class="feed-lists">
                            <h1><i class="fa fa-bolt" aria-hidden="true"></i> Latest published</h1>
                            {latest}
                        </div>
                    </td>
                </tr>
            </table>
            <br>

            <!-- Folders -->
            <div id="folders">
                {categories_html}
            </div>
        <br>
        </div>
    </main>

    <footer class="footer">
        <br><div>&copy 2015-2023 <a href="http://idiomind.sourceforge.net">idiomind</a> Project | <a href="http://idiomind.sourceforge.net/contact">Contact</a> | <a href="../privacypolicy.htm">Privacy</a><br><a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/"><a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike</a>.
        </div><br>
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


def generate_lang_app(lang, categories):
    """Generate the app home page for a language."""
    uplang = lang.capitalize()
    cat_boxes = []
    for cat_name, idmnd_files in categories:
        count = len(idmnd_files)
        if count > 0:
            cat_boxes.append(generate_category_item(
                lang, cat_name, count, "appbox.html",
                cls="box category-item", attrs=f'title="{esc(cat_name)}"'))

    categories_html = "\n".join(cat_boxes)

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="">
<meta name="author" content="">
<meta name="keywords" content="ESL, EFL, pronunciation, grammar, vocabulary, tests, lessons, quiz, quizzes, resources, lesson, vocabulary, questions, answers"/>
<meta name="description" content="Learn foreign vocabulary"/>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<link rel="shortcut icon" href="/favicon.ico?v=2" type="image/x-icon">
<link rel="icon" type="image/png" href="/favicon-32x32.png" sizes="32x32" />
<link rel="icon" type="image/png" href="/favicon-16x16.png" sizes="16x16" />
<link rel="image_src" href="https://idiomind.sourceforge.io/images/logo.png" /><!--formatted-->
<title>Idiomind's library</title>
<link href="/css/apphome.css" rel="stylesheet" type="text/css" />
<link href="/css/fa/css/font-awesome.css" rel="stylesheet" type="text/css" />

<script>
function setCookie() {{
    var d = new Date();
    d.setTime(d.getTime() + (30*24*60*60*1000));
    var expires = "expires=" + d.toGMTString();
    document.cookie="language={esc(lang)}; expires=" + expires + "; path=/";
}}
</script>

<script type="text/javascript" src="http://ajax.googleapis.com/ajax/libs/jquery/1.4/jquery.min.js"></script>
<script type="text/javascript" src="/js/fancybox/jquery.fancybox-1.3.4.pack.js"></script>
<link rel="stylesheet" type="text/css" href="/js/fancybox/jquery.fancybox-1.3.4.css" media="screen" />

<script type="text/javascript">
        $(document).ready(function() {{
            $(".box").fancybox({{
                "width"         : "100%",
                "height"        : "100%",
                "margin"        : 15,
                "padding"        : 10,
                'autoScale'     : false,
                'transitionIn'      : 'none',
                'transitionOut'     : 'none',
                'overlayColor'      : '#ECEEF1',
                'overlayOpacity'    : 0,
                'scrolling'     : 'yes',
                'type'          : 'iframe',
                'titlePosition': 'inside'
            }});
        }});
</script>

    {GA_SNIPPET}
</head>
<body onload="setCookie()">

    <main id="content" class="group" role="main">
    <div class="main">

    {generate_library_header(lang, uplang)}
    <div id="categories">
    {categories_html}
    </div>
  </div>
  </main>
</body>
</html>"""


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


def generate_mobilebox(lang, cat_name, idmnd_files):
    """Generate the mobile category listing page."""
    rows = []
    for f in sorted(idmnd_files, key=lambda x: x.name.lower()):
        name = f.stem
        rows.append(f"""<tr style="width:5%;height:65px;">
            <td style="width:5%"><a href="/{lang}/mobileview.html?l={url_quote(lang)}&c={url_quote(cat_name)}&set={url_quote(name)}"><img class='expand' src='/images/idmnd.png'></a></td>
            <td style="width:90%"><a href="/{lang}/mobileview.html?l={url_quote(lang)}&c={url_quote(cat_name)}&set={url_quote(name)}">{esc(name)}</a></td>
        </tr>""")

    rows_html = "\n".join(rows)

    return f"""<!doctype html>
<html>
<head>
   <meta charset="UTF-8">
   <link rel="shortcut icon" href="/favicon.ico">
   <title>Topics</title>
   <link rel="stylesheet" href="/css/mobilebox.css">
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


def generate_appbox(lang, cat_name, idmnd_files):
    """Generate the app category listing page."""
    rows = []
    for f in sorted(idmnd_files, key=lambda x: x.name.lower()):
        name = f.stem
        rows.append(f"""<tr>
            <td style="width:5%"><a href="/{lang}/appview.html?l={url_quote(lang)}&c={url_quote(cat_name)}&set={url_quote(name)}"><img class='expand' src='/images/idmnd.png'></a></td>
            <td style="width:90%;line-height:16px;font-size:13px"><a href="/{lang}/appview.html?l={url_quote(lang)}&c={url_quote(cat_name)}&set={url_quote(name)}">{esc(name)}</a></td>
        </tr>""")

    rows_html = "\n".join(rows)

    return f"""<!doctype html>
<html>
<head>
   <meta charset="UTF-8">
   <link rel="shortcut icon" href="/favicon.ico">
   <title>Topics</title>
   <link rel="stylesheet" href="/css/appbox.css">
   <script src="/js/sorttablee.js"></script>
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
        <meta charset="utf-8"/>
        <title>Study</title>
        <meta name="description" content="Flashcards"/>
        <link rel="stylesheet" href="{css_file}"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <link rel="stylesheet" href="/css/sweetalert.css"/>

        <script type="text/javascript"> //  Loading gif
            function onReady(callback) {{
                var intervalID = window.setInterval(checkReady, 800);

                function checkReady() {{
                    if (document.getElementsByTagName('body')[0] !== undefined) {{
                        window.clearInterval(intervalID);
                        callback.call(this);
                    }}
                }}
            }}

            function show(id, value) {{
                document.getElementById(id).style.display = value ? 'block' : 'none';
            }}

            onReady(function () {{
                show('page', true);
                show('loading', false);
            }});
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
                var bol = faves.includes(data.name);

                if(bol == true)
                {{
                    var SetFavs_value = faves.replace(data.name+'|','');
                    var expiration_date = new Date();
                    expiration_date.setFullYear(expiration_date.getFullYear() + 1);
                    var expires = "expires=" + expiration_date.toGMTString();
                    document.cookie=cookie_name+"="+SetFavs_value+"; expires=" + expires + "; path=/";
                    el.src='/images/fav.png';
                }}
                else
                {{
                    SetFavs_value = data.name+'|'+faves
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

                if(data.name == lessonChk)
                {{
                    var expiration_date = new Date();
                    expiration_date.setFullYear(expiration_date.getFullYear() + 1);
                    var expires = "expires=" + expiration_date.toGMTString();
                    document.cookie="topic_study="+SetFavs_value+"; expires=" + expires + "; path=/";
                    el.src='/images/pin.png';
                }}
                else
                {{
                    SetFavs_value = data.name
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
                <table class="topic_info">
                    <tr>
                        <td>
                           <div id="name" class="topicName">
                                <h1 style="font-weight:bold;font-family:Verdana;font-size:20px;font-size:1.50vw;"></h1>
                            </div>
                            <span id="levl">This topic is aimed for <b><font></font></b> students.</span><br>
                            <span>Contains: </span>
                            <span id="nwrd"><font></font></span>
                            <span id="nsnt"><font></font></span>
                            <span id="naud"><font></font></span>
                            <span id="nimg"><font></font></span>
                        </td>
                    </tr>
                    <tr>
                      <td>Translations: <span style="text-align:left;"id="slng"><font ></font></span> <br>
                          It was uploaded on <span style="text-align:left;"id="dteu"><font></font></span>
                          <span style="text-align:left;"id="autr"> by <font ></font>.
                           <b><a href="#" id="downloadLink">Download</a></b>
                          </span>
                      </td>
                    </tr>
                </table>
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
                        <span style="background-color:#D47D85;border-radius:4px;padding:5px;box-shadow: 2px 2px 2px rgba(0, 0, 0, 0.2);" id="score_no"> I did not know it:  <font></font></span>  &nbsp;&nbsp;
                        <span style="background-color:#86C754;border-radius:4px;padding:5px;box-shadow: 2px 2px 2px rgba(0, 0, 0, 0.2);" id="score_ok">I knew it:  <font></font></span>
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
            <div class="note" id="info_note">
                <p style="color:#4A4A4A;"></p>
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
                <input class="btnNo" id="Wrong" type="button" value="0" onclick="doFunction();" />
                <input style="display: inline-block;" class="btnShow" id="Show" type="button" value="Show translation" onclick="doFunction();" />
                <input class="btnOk" id="Right" type="button" value="0" onclick="doFunction();" />
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


def generate_mobileview(lang):
    """Generate the mobile view page."""
    return generate_view(lang, css_file="/css/mobileview.css", js_file="/js/view_mob.js").replace(
        "images/back_grey.png", "images/backgrey.png"
    ).replace(
        "id=\"goBack\"", "id=\"goBack\""
    )


def generate_favs(lang):
    """Generate the favorites page (100% JavaScript)."""
    return f"""<!doctype html>
<html>
<head>
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


def generate_mobilefavs(lang):
    """Generate the mobile favorites page."""
    return f"""<!doctype html>
<html>
<head>
   <meta charset="UTF-8">
   <link rel="shortcut icon" href="/favicon.ico">
   <title>Topics</title>
   <link rel="stylesheet" href="/css/mobilebox.css">
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
            tr.innerHTML = '<td style="width:5%"><a href="/{esc(lang)}/mobileview.html?l={esc(lang)}&c=fav&set=' + encodeURIComponent(fav) + '"><img class="expand" src="/images/idmnd.png"></a></td>' +
                '<td style="width:90%"><a href="/{esc(lang)}/mobileview.html?l={esc(lang)}&c=fav&set=' + encodeURIComponent(fav) + '">' + fav + '</a></td>';
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
<head><meta http-equiv="Content-Type" content="text/html; charset=windows-1252">
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

    <script>
    (function(){
        var ua = navigator.userAgent;
        if (/Windows Phone|iPhone|Android/i.test(ua)) {
            window.location.href = '/mobile.html';
        }
    })();
    </script>

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
                <a class="site-nav-link" href="contact.html" onfocus="this.blur();">Contact</a>
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
        <p>&copy; 2023 <a href="https://idiomind.sourceforge.io">Idiomind Project</a></p>
    </footer>

</body>

</html>
"""


def generate_mobile_root():
    """Generate the root mobile.html page."""
    return """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Idiomind</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="keywords" content="learn english free, learn english, learn english online, learn english grammar, learn english vocabulary, free English lessons, basic english, english vocabulary, english dictation, business english, english as a second language, english as a foreign language, english spelling, english grammar, english dictation, ESL, EFL, pronunciation, grammar, vocabulary, tests, lessons, quiz, quizzes, resources, lesson, vocabulary, questions, answers"/>
    <meta name="description" content="Idiomind is a valuable tool for language learners seeking to enhance their language skills."/>
    <link href="./css/bootstrap.css" rel="stylesheet">
    <link href="./css/bootstrap-responsive.css" rel="stylesheet">
    <link rel="shortcut icon" href="/favicon.ico?v=2" type="image/x-icon">
    <link rel="icon" type="image/png" href="favicon-32x32.png" sizes="32x32"/>
    <link rel="icon" type="image/png" href="favicon-16x16.png" sizes="16x16"/>
    <link rel="image_src" href="/images/logo.png"/><!--formatted-->

    <link href='https://fonts.googleapis.com/css?family=Source+Sans+Pro:200,300,400,600' rel='stylesheet' type='text/css'>
    <link href="./css/css" rel="stylesheet" type="text/css">

    <script>
        (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
        (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
        m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
        })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

        ga('create', 'UA-63037434-3', 'auto');
        ga('send', 'pageview');
    </script>

</head>

<body>
    <div class="container">
        <div class="row">
            <div class="span6">
                <h1><a href="/mobile.html">Idiomind</a></h1>
                <p>Idiomind is a tool for language learners seeking to enhance their language skills.</p>
                <div style="text-align: right;font-size: 1.0em;"><a href="/donatem.html">Donate</a></div><br><br>
                 <p>
                    Language learners are always in search of new words and phrases. Idiomind can assist you in your language learning journey by allowing you to save and practice the words and phrases you come across every day.
                </p>
                <br>
                <h3>
                    Features
                </h3>

                <p>
                    <ul>
                    <li>Take notes on the go</li>
                    <li>Words and phrases pronunciation</li>
                    <li>Automatic translation using Google Translate</li>
                    <li>Practices</li>
                    <li>Track your progress through reviews to reinforce your learning</li>
                    <li>Customize up to 10 languages to learn</li>
                    <li>User-friendly interface available in English, Spanish, Portuguese, French, and Italian</li>
                    </ul>
                </p>
                <br>
                <h3>
                    Usage Example

                </h3>

                <p>Usage Example: Taking note of words and sentences from a PDF document<br>
                Here is an example of how to take notes on words and sentences from a PDF document using Idiomind:</p><br><br>
                    <iframe width="285" height="160" src="https://www.youtube.com/embed/HFvcQjlVHcA?rel=0&showinfo=0" frameborder="0" allowfullscreen></iframe>
                </p>

                <br>
                <h3>
                    Install / Download
                </h3>

                <p>You can install Idiomind through the terminal using the following commands:<br></p>
                <p><code>add-apt-repository ppa:robinpalat/idiomind<br>
                apt-get update<br>
                apt-get install idiomind</code>
                </p>
             <br>
                <p>
                    Alternatively, you can download it from sourceforge.net.<br>However, the recommended method is to use the above commands for installation. </p>
                    <a href="https://sourceforge.net/projects/idiomind/files/latest/download"><img alt="Download Idiomind" src="https://a.fsdn.com/con/app/sf-download-button" width=276 height=48 srcset="https://a.fsdn.com/con/app/sf-download-button?button_size=2x 2x"></a>

                <br><br><br>
                <h3>Support or contact</h3><br>
                <p><a href="/helpm.html">Getting started with idiomind</a></p><br>
                <p><a href="/library.html">Topic Library</a></p><br>
                <p><a href="/contactm.html">Send a message</a></p><br>
                <br>
                <footer>
                &copy; 2023 <a href="https://idiomind.sourceforge.io">Idiomind Project </a></small>
                </footer>
            </div>
        </div>
    </div>
    <br>

</body>
</html>"""


def generate_search():
    """Generate the search page and search index."""
    search_html = """<!DOCTYPE html>
<html>
<head>
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
        .search-result { padding: 10px; border-bottom: 1px solid #eee; }
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
    <meta charset="utf-8">
    <title>News</title>
    <meta http-equiv="refresh" content="0;url=page1.html">
    <script>window.location.href='page1.html';</script>
</head>
<body>
    <p>Redirecting to <a href="page1.html">News</a>...</p>
</body>
</html>"""


def copy_static_files():
    """Copy static files from source to dist."""
    dist = DIST_DIR

    # CSS
    src = BASE_DIR / "css"
    if src.is_dir():
        shutil.copytree(src, dist / "css", dirs_exist_ok=True)

    # JS
    src = BASE_DIR / "js"
    if src.is_dir():
        shutil.copytree(src, dist / "js", dirs_exist_ok=True)

    # Images
    src = BASE_DIR / "images"
    if src.is_dir():
        shutil.copytree(src, dist / "images", dirs_exist_ok=True)

    # Share (may contain symlinks to external dirs)
    src = BASE_DIR / "share"
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
    src = BASE_DIR / "Files"
    if src.is_dir():
        shutil.copytree(src, dist / "Files", dirs_exist_ok=True)

    # Static HTML pages
    for fname in STATIC_HTML:
        src = BASE_DIR / fname
        if src.is_dir():
            shutil.copytree(src, dist / fname, dirs_exist_ok=True)
        elif src.is_file():
            shutil.copy2(src, dist / fname)

    # Favicons
    for fname in ["favicon.ico", "favicon-16x16.png", "favicon-32x32.png", "favicon32.ico"]:
        src = BASE_DIR / fname
        if src.is_file():
            shutil.copy2(src, dist / fname)

    # Root images (dona.png, donat.png, done.png)
    for fname in ["dona.png", "donat.png", "done.png"]:
        src = BASE_DIR / fname
        if src.is_file():
            shutil.copy2(src, dist / fname)

    # News pages
    news_dist = dist / "news"
    news_dist.mkdir(exist_ok=True)
    for fname in ["page1.html", "page2.html"]:
        src = BASE_DIR / "news" / fname
        if src.is_file():
            shutil.copy2(src, news_dist / fname)


def copy_idmnd_files(lang, lang_dir, dist_lang):
    """Copy all .idmnd files preserving directory structure."""
    for f in lang_dir.rglob("*.idmnd"):
        rel = f.relative_to(lang_dir)
        dest = dist_lang / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)


def generate_doc_pages():
    """Generate the doc/ pages (doc/index.html + doc/feedback/)."""

    # --- doc/index.html ---
    # Based on doc/index.php but static: strip PHP, inject mobile JS,
    # remove dead rss_releases include, rewrite .php links.
    doc_src = BASE_DIR / "doc" / "index.php"
    if doc_src.is_file():
        content = doc_src.read_text(encoding="utf-8", errors="replace")

        # Remove any PHP blocks (mobile detection + rss_releases include)
        content = re.sub(r"<\?php.*?\?>", "", content, flags=re.S)

        # Fix class="current_category" anchor to index.html
        content = content.replace('href="index.php"', 'href="index.html"')

        # These pages live at the site root, not under /doc/. Fix relative refs.
        for name in ["help.html", "library.html", "contact.html"]:
            content = content.replace(f'href="{name}"', f'href="/{name}"')
        for name in ["favicon-32x32.png", "favicon-16x16.png", "favicon.ico"]:
            content = content.replace(f'href="{name}"', f'href="/{name}"')
            content = content.replace(f'src="{name}"', f'src="/{name}"')

        # Fix /news?page=1 -> /news/index.html (news redirect)
        content = content.replace('href="/news?page=1"', 'href="/news/index.html"')
        content = content.replace('href="/news?page=1">', 'href="/news/index.html">')

        # Inject mobile detection before </head>
        mobile_js = """
    <script>
    (function(){
        var ua = navigator.userAgent;
        if (/Windows Phone|iPhone|Android/i.test(ua)) {
            window.location.href = '/mobile.html';
        }
    })();
    </script>
</head>"""
        content = content.replace("</head>", mobile_js, 1)

        doc_dist = DIST_DIR / "doc"
        doc_dist.mkdir(parents=True, exist_ok=True)
        (doc_dist / "index.html").write_text(content, encoding="utf-8")
        print("  Generated doc/index.html")

    # --- doc/feedback/index.html + rss.xml ---
    # rg_NOTE: original is an RSS generator over .txt feedback files.
    # We generate a static rss.xml at build time and a simple index.html viewer.
    fb_dir = BASE_DIR / "doc" / "feedback"
    if fb_dir.is_dir():
        fb_dist = DIST_DIR / "doc" / "feedback"
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
<head>
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
<span><p><small>&copy; 2019 <a href="https://idiomind.sourceforge.io">Idiomind Project</a></small></p></span>
</div>
</body>
</html>"""
        (fb_dist / "index.html").write_text(fb_html, encoding="utf-8")
        print(f"  Generated doc/feedback/index.html + rss.xml ({len(items)} feedback items)")


def fix_php_references():
    """Fix .php references in copied static HTML files in dist/."""
    import re

    # Mapping of .php references to their static equivalents
    replacements = [
        # Root pages
        (r'href="index\.php"', 'href="index.html"'),
        (r"href='index\.php'", "href='index.html'"),
        (r'href="/index\.php"', 'href="/index.html"'),
        (r'href="mobile\.php"', 'href="mobile.html"'),
        (r'href="/mobile\.php"', 'href="/mobile.html"'),
        (r'href="\.\./index\.php"', 'href="../index.html"'),
        (r'href="\.\./\.\./index\.php"', 'href="../../index.html"'),
        (r'action="/sub\.php"', 'action="https://forms.gle/REPLACE_WITH_REAL_FORM"'),
    ]

    for html_file in DIST_DIR.rglob("*.html"):
        try:
            content = html_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        original = content
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        if content != original:
            html_file.write_text(content, encoding="utf-8")
            rel = html_file.relative_to(DIST_DIR)
            print(f"  Fixed .php refs in: {rel}")


def fix_broken_refs():
    """Fix broken references in copied static HTML files."""
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

    for html_file in DIST_DIR.rglob("*.html"):
        try:
            content = html_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        original = content

        # Fix ./css/css -> /css/ (bug in original mobile templates)
        content = content.replace('href="./css/css"', 'href="/css/classic.css"')

        # Fix relative favicon paths in news/ pages
        rel_path = html_file.relative_to(DIST_DIR)
        if str(rel_path).startswith("news/"):
            content = content.replace('href="favicon-32x32.png"', 'href="/favicon-32x32.png"')
            content = content.replace('href="favicon-16x16.png"', 'href="/favicon-16x16.png"')
            content = content.replace('href="favicon.ico"', 'href="/favicon.ico"')
            content = content.replace("href='favicon.ico'", "href='/favicon.ico'")
            content = content.replace('href="favicon.ico?v=2"', 'href="/favicon.ico?v=2"')

        # Fix fancybox v1 refs -> v2 (app.html templates)
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
        # mobilebox.html and appbox.html
        content = re.sub(
            r'/([\w]+)/mobilebox\.html\?lang=[^"&]+&category=([^"&]+)',
            fix_box_link,
            content
        )
        content = re.sub(
            r'/([\w]+)/appbox\.html\?lang=[^"&]+&category=([^"&]+)',
            fix_box_link,
            content
        )

        if content != original:
            html_file.write_text(content, encoding="utf-8")
            rel = html_file.relative_to(DIST_DIR)
            print(f"  Fixed broken refs in: {rel}")


def build():
    """Main build function."""
    print("=" * 60)
    print("  Idiomind Static Site Builder")
    print("=" * 60)

    # Clean dist
    if DIST_DIR.exists():
        print(f"Cleaning {DIST_DIR}...")
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    # Discover languages
    languages = find_languages()
    print(f"\nLanguages found: {', '.join(languages)}")

    # Store data for search index generation
    languages_data = []

    # Copy static files
    print("\nCopying static files...")
    copy_static_files()

    # Generate root pages
    print("Generating root index.html...")
    (DIST_DIR / "index.html").write_text(generate_root_index(), encoding="utf-8")

    print("Generating root mobile.html...")
    (DIST_DIR / "mobile.html").write_text(generate_mobile_root(), encoding="utf-8")

    # Generate news redirect
    print("Generating news/index.html...")
    (DIST_DIR / "news" / "index.html").write_text(generate_news_index(), encoding="utf-8")

    # Generate search
    print("Generating search.html...")
    (DIST_DIR / "search.html").write_text(generate_search(), encoding="utf-8")

    # Generate per-language content
    for lang in languages:
        lang_dir = BASE_DIR / lang
        dist_lang = DIST_DIR / lang
        dist_lang.mkdir(parents=True, exist_ok=True)

        categories = find_categories(lang_dir)
        languages_data.append((lang, categories))

        cat_count = len(categories)
        file_count = sum(len(files) for _, files in categories)
        print(f"\n--- {lang} ({cat_count} categories, {file_count} .idmnd files) ---")

        # Generate home pages
        print(f"  Generating {lang}/index.html...")
        (dist_lang / "index.html").write_text(generate_lang_index(lang, categories), encoding="utf-8")

        print(f"  Generating {lang}/mobile.html...")
        (dist_lang / "mobile.html").write_text(generate_lang_mobile(lang, categories), encoding="utf-8")

        print(f"  Generating {lang}/app.html...")
        (dist_lang / "app.html").write_text(generate_lang_app(lang, categories), encoding="utf-8")

        # Generate view pages (same for all categories)
        print(f"  Generating {lang}/view.html...")
        (dist_lang / "view.html").write_text(generate_view(lang), encoding="utf-8")

        print(f"  Generating {lang}/mobileview.html...")
        (dist_lang / "mobileview.html").write_text(generate_mobileview(lang), encoding="utf-8")

        print(f"  Generating {lang}/appview.html...")
        (dist_lang / "appview.html").write_text(generate_view(lang, css_file="/css/appview.css", js_file="/js/view.js"), encoding="utf-8")

        # Generate favs pages
        print(f"  Generating {lang}/favs.html...")
        (dist_lang / "favs.html").write_text(generate_favs(lang), encoding="utf-8")

        print(f"  Generating {lang}/mobilefavs.html...")
        (dist_lang / "mobilefavs.html").write_text(generate_mobilefavs(lang), encoding="utf-8")

        # Generate RSS
        print(f"  Generating {lang}/rss.xml...")
        (dist_lang / "rss.xml").write_text(generate_rss_xml(lang, categories), encoding="utf-8")

        # Generate per-category pages
        for cat_name, idmnd_files in categories:
            cat_dir = dist_lang / cat_name
            cat_dir.mkdir(parents=True, exist_ok=True)

            print(f"  Generating {lang}/{cat_name}/index.html ({len(idmnd_files)} topics)...")
            (cat_dir / "index.html").write_text(generate_box(lang, cat_name, idmnd_files), encoding="utf-8")

            # Mobile and app versions
            (cat_dir / "mobile.html").write_text(generate_mobilebox(lang, cat_name, idmnd_files), encoding="utf-8")
            (cat_dir / "app.html").write_text(generate_appbox(lang, cat_name, idmnd_files), encoding="utf-8")

        # Copy .idmnd files
        print(f"  Copying .idmnd files...")
        copy_idmnd_files(lang, lang_dir, dist_lang)

    # Generate the root library page (language picker + topic grid by cookie)
    print("\nGenerating library.html...")
    (DIST_DIR / "library.html").write_text(generate_library_page(languages_data), encoding="utf-8")

    # Generate search index
    print("\nGenerating search-index.json...")
    (DIST_DIR / "search-index.json").write_text(generate_search_index(languages_data), encoding="utf-8")

    # Generate global RSS
    print("Generating global rss.xml...")
    all_cats = []
    for lang in languages:
        lang_dir = BASE_DIR / lang
        all_cats.extend(find_categories(lang_dir))
    (DIST_DIR / "rss.xml").write_text(generate_rss_xml("_global_", all_cats), encoding="utf-8")

    # Post-process: fix .php references in copied static HTML files
    print("\nPost-processing: fixing references in static HTML files...")
    fix_php_references()
    fix_broken_refs()

    # Keep the repository copy of library.html in sync with the generated page
    (BASE_DIR / "library.html").write_text(
        (DIST_DIR / "library.html").read_text(encoding="utf-8"), encoding="utf-8")

    # Generate doc/ pages (not part of language tree)
    print("\nGenerating doc pages...")
    generate_doc_pages()

    # Summary
    total_files = sum(1 for _ in DIST_DIR.rglob("*") if _.is_file())
    print(f"\n{'=' * 60}")
    print(f"  Build complete!")
    print(f"  Output: {DIST_DIR}")
    print(f"  Total files: {total_files}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    build()
