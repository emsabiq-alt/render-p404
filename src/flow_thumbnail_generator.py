"""Generate world-class YouTube thumbnail variants in Google Flow via CDP.

Features:
- Masterwork 19th-century copperplate intaglio etching with modern cinematic chiaroscuro
- Fiery copper/amber rim-lighting and volcanic embers for intense dynamic range (Project 404 grade)
- Deep dark vignettes and pristine, bold condensed headline typography rendered directly in Flow
- 3 mobile-safe (<=55 chars) viral titles in all-caps
- Formatted YouTube description, chapters, and Kevin MacLeod CC-BY credits
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

FLOW_SRC = Path("D:/project/a043/src")
if str(FLOW_SRC) not in sys.path:
    sys.path.insert(0, str(FLOW_SRC))

from flow_automator import GoogleFlowClient  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "export" / "thumbnail_flow"
META = OUT / "thumbnail_flow_pack.json"

VIRAL_TITLES = [
    "LEDAKAN SAMALAS 1257: KIAMAT YANG MEMBEKUKAN DUNIA",
    "LEBIH DAHSYAT DARI KRAKATAU: MONSTER LOMBOK 1257",
    "KOTA KUNO YANG LENYAP: KIAMAT TOTAL SAMALAS 1257",
]

THUMBNAIL_HOOKS = [
    "1257: DUNIA MEMBEKU",
    "LEBIH DARI KRAKATAU",
    "HILANG DALAM SEKEJAP",
]


def prompt_for_variant(idx: int) -> str:
    hook = THUMBNAIL_HOOKS[idx]

    if idx == 0:
        visual = """
An epic apocalyptic cinematic view of the colossal Mount Samalas super-eruption in 1257: a titanic 43-kilometer Plinian volcanic column violently blasting into the stratosphere, forming an enormous ominous black umbrella ash cloud that eclipses the sun. Brilliant spiderweb volcanic lightning bolts arcing through the dense churning charcoal ash plumes. The shattered volcanic caldera glowing with fiery molten copper magma fissures (#FF7700) along the crater rim, contrasting against deep charcoal-black ash plumes and pitch-black ink shadows. Luminous golden embers and volcanic sparks drifting through the air. Below, the ancient coastal silhouettes of Lombok rendered in exquisite microscopic cross-hatching and fine burin stippling.
""".strip()
    elif idx == 1:
        visual = """
A dramatic split-scale forensic mystery composition: an antique cracked 13th-century world map with sulfur fallout trails spreading across medieval continents, juxtaposed with the monstrous glowing caldera of Mount Samalas violently rupturing its peak in Lombok. Glowing fiery copper lava fountains, dark etched ocean waves, ancient cartographic compass roses, and cross-sections of polar ice cores revealing deep dark volcanic ash strata. Intense chiaroscuro contrast with deep pitch-black ink shadows and luminous glowing amber highlights.
""".strip()
    else:
        visual = """
A gripping forensic historical catastrophe scene: the ancient medieval royal city of Pamatan being engulfed by a colossal glowing wall of pyroclastic surge and raining volcanic tephra from Mount Samalas looming ominously in the background. Ancient wooden tiered palace pavilions and stone shrines crumbling into fiery glowing ash, silhouette of an ancient Sasak chronicler clutching palm leaf lontar manuscripts in the foreground looking back at the apocalyptic doom. Volumetric firelight, glowing golden embers, heavy chiaroscuro.
""".strip()

    prompt = f"""
Masterpiece 19th-century archival copperplate intaglio etching and fine steelpoint engraving on aged heavy-weight tea-stained cream parchment paper (#EBD8B1).
High dynamic range cinematic chiaroscuro color grade: deep rich carbon-black ink shadows (#0A0705), warm sepia tones, and glowing fiery molten copper/amber highlights (#FF8C00). Intense dark vignette on all four corners framing the focal center. Royal Geographical Society archival expedition plate aesthetic, breathtaking scale and scientific grandeur.

{visual}

At the bottom center of the composition, a prominent bold graphic design documentary title in massive condensed sans-serif block letters reading:
"{hook}"
Typography specifications: pristine bold condensed poster font (Bebas Neue aesthetic), razor-sharp solid vector edges, pure flat ivory-white letters (#FFFFFF) with an authoritative bold dark charcoal outline and subtle black drop shadow. Perfectly straight horizontal baseline, centered, clean, zero distortion, zero handwriting, zero extra text, with generous margin from the edges. Full bleed 16:9 widescreen composition, borderless.
""".strip()
    return prompt


def get_description() -> str:
    return """SAMALAS 1257 adalah letusan vulkanik terbesar dalam 7.000 tahun terakhir yang mengubah peradaban dunia. Dari pulau Lombok, letusan berkekuatan VEI-7 ini memuntahkan 40 kilometer kubik magma, menyemburkan kolom abu setinggi 43 kilometer, dan menyelimuti atmosfer bumi dengan kabut belerang global yang memicu Tahun Tanpa Musim Panas (Year Without a Summer) di Eropa dan Asia.

Dokumenter ini merangkai bukti geologi modern, jejak sulfur di inti es kutub Greenland-Antarktika, ekskavasi kuburan massal di London, dan naskah kuno Babad Lombok untuk mengungkap misteri hilangnya metropolis kuno Pamatan.

CHAPTERS
00:00 PROLOG — JEJAK ABU DI LANGIT DUNIA
00:04 BAB 1 — LOMBOK SEBELUM 1257
02:54 BAB 2 — KALDERA YANG MELEDAK
05:48 BAB 3 — MUSIM DINGIN TANPA MATAHARI
08:42 BAB 4 — BUKTI ILMIAH DI ES DAN TANAH
11:36 BAB 5 — WARISAN SAMALAS
14:18 PENUTUP

CREDIT MUSIK
- Ossuary 5 - Rest by Kevin MacLeod (incompetech.com)
  Licensed under Creative Commons: By Attribution 4.0 License
  http://creativecommons.org/licenses/by/4.0/
- Prelude and Action by Kevin MacLeod (incompetech.com)
  Licensed under Creative Commons: By Attribution 4.0 License
  http://creativecommons.org/licenses/by/4.0/

CREDIT PRODUKSI
Production: Banyak Tau Studio
Voice Over: Supertonic v3 (Indonesian M2 - 91.9 Hz)
Visual Architecture: 19th-Century Copperplate Etching & Archival Sepia Lithograph (Project 404 Style)
Master Film: 1920x1080 30fps Full-Bleed Borderless

#Samalas1257 #GunungSamalas #SejarahNusantara #Geologi #DokumenterIndonesia #BanyakTau #Project404"""


def flow_image_sources(client):
    script = r'''
(() => Array.from(document.images)
  .map(i => i.src)
  .filter(Boolean)
  .filter(s => s.includes('flow.google.com/asb/') || s.includes('flow-content.google/image/'))
)()
'''
    return client.evaluate_js(script) or []


def download_url(url, out_path):
    req = urllib.request.Request(
        url.replace('&amp;', '&'),
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://flow.google.com/"},
    )
    with urllib.request.urlopen(req, timeout=90) as r, open(out_path, "wb") as f:
        f.write(r.read())


def generate_one_thumbnail(client, prompt: str, out_path: Path, timeout: int = 150) -> str:
    before = set(flow_image_sources(client))

    # Focus and clear ProseMirror
    client.evaluate_js("""
    (() => {
        const editor = document.querySelector('.ProseMirror[contenteditable="true"]');
        if (editor) {
            editor.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
            return true;
        }
        return false;
    })()
    """)
    time.sleep(0.4)
    client._send("Input.insertText", {"text": prompt})
    time.sleep(0.5)
    client.evaluate_js("""
    (() => {
        const editor = document.querySelector('.ProseMirror');
        if (editor) {
            editor.dispatchEvent(new Event('input', {bubbles: true}));
            editor.dispatchEvent(new Event('change', {bubbles: true}));
        }
    })()
    """)
    time.sleep(0.4)

    coords = client.evaluate_js("""
    (() => {
        const btn = document.querySelector('button[aria-label="Start generation"]');
        if (!btn) return null;
        const r = btn.getBoundingClientRect();
        return {x: r.left + r.width / 2, y: r.top + r.height / 2, disabled: btn.disabled};
    })()
    """)
    if coords and not coords.get("disabled"):
        client._send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": coords["x"], "y": coords["y"], "button": "left", "clickCount": 1})
        client._send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": coords["x"], "y": coords["y"], "button": "left", "clickCount": 1})
        print("  → Generation triggered in Google Flow. Waiting for new render...")
    else:
        raise RuntimeError("Tombol Start generation tidak aktif di Google Flow")

    start = time.time()
    while time.time() - start < timeout:
        time.sleep(4)
        now = flow_image_sources(client)
        new = [u for u in now if u not in before]
        if new:
            download_url(new[0], str(out_path))
            print(f"  ✓ Thumbnail saved: {out_path} ({out_path.stat().st_size} bytes)")
            return str(out_path)

    raise TimeoutError(f"Flow tidak menghasilkan gambar baru dalam {timeout}s")


def run_full_generation():
    OUT.mkdir(parents=True, exist_ok=True)
    client = GoogleFlowClient()
    client.connect()

    results = []
    try:
        for idx in range(3):
            out_file = OUT / f"thumbnail_FLOW_AB_{idx+1}.png"
            title = VIRAL_TITLES[idx]
            hook = THUMBNAIL_HOOKS[idx]
            prompt = prompt_for_variant(idx)

            print(f"\n=======================================================")
            print(f" GENERATING FLOW THUMBNAIL [{idx+1}/3]: {hook}")
            print(f" Title: {title}")
            print(f"=======================================================")

            generate_one_thumbnail(client, prompt, out_file)
            results.append({
                "variant": f"A/B {idx+1}",
                "hook": hook,
                "title": title,
                "path": str(out_file).replace("\\", "/"),
                "prompt": prompt
            })
            if idx < 2:
                print("  ⏳ Resting 8s between requests...")
                time.sleep(8)
    finally:
        client.close()

    metadata = {
        "method": "Google Flow via CDP/MCP flow automation (Hyper-Comprehensive Chiaroscuro Etching Prompts)",
        "titles": VIRAL_TITLES,
        "hooks": THUMBNAIL_HOOKS,
        "thumbnails": results,
        "description": get_description(),
        "chapters": [
            {"time": "00:00", "title": "PROLOG — JEJAK ABU DI LANGIT DUNIA"},
            {"time": "00:04", "title": "BAB 1 — LOMBOK SEBELUM 1257"},
            {"time": "02:54", "title": "BAB 2 — KALDERA YANG MELEDAK"},
            {"time": "05:48", "title": "BAB 3 — MUSIM DINGIN TANPA MATAHARI"},
            {"time": "08:42", "title": "BAB 4 — BUKTI ILMIAH DI ES DAN TANAH"},
            {"time": "11:36", "title": "BAB 5 — WARISAN SAMALAS"},
            {"time": "14:18", "title": "PENUTUP"},
        ],
        "music_credit": [
            "Ossuary 5 - Rest by Kevin MacLeod (incompetech.com), CC BY 4.0",
            "Prelude and Action by Kevin MacLeod (incompetech.com), CC BY 4.0",
        ]
    }
    META.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ Metadata updated at {META}")
    return metadata


if __name__ == "__main__":
    data = run_full_generation()
    print("SUCCESS! Generated 3 Flow thumbnails with comprehensive chiaroscuro prompts.")
