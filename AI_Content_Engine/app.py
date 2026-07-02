"""
app.py - AI Multimodal Content Engine (Streamlit)
"""

import json
import logging
import time
from typing import Any

import streamlit as st

from config import SUPPORTED_TONES
from text_gen import generate_tagline, generate_blog_intro, generate_social_posts
from image_gen import build_image_prompt, generate_image
from video_gen import generate_video

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(page_title="AI Content Engine", page_icon=":sparkles:", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .card { background: white; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid #e9ecef; }
    .card h3 { margin-top: 0; color: #212529; font-weight: 600; }
    .card p, .card div { color: #495057; }
    .success-badge { display: inline-block; background: #d3f9d8; color: #2b8a3e; padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-left: 0.5rem; }
    .stButton>button { background: #4263eb; color: white; border-radius: 8px; padding: 0.5rem 2rem; font-weight: 600; border: none; }
    .stButton>button:hover { background: #3b5bdb; }
    hr { margin: 2rem 0; }
</style>""", unsafe_allow_html=True)

st.title(":sparkles: AI Multimodal Content Engine")
st.markdown('<p style="color: #868e96; margin-top: -0.5rem;">Generate campaign taglines, blog intros, social posts, hero images, and promotional videos - all in one pipeline.</p>', unsafe_allow_html=True)

if "generated" not in st.session_state:
    st.session_state.generated = False
    st.session_state.results: dict[str, Any] = {}

with st.sidebar:
    st.markdown("## Campaign Brief")
    product_name = st.text_input("Product Name", placeholder="e.g. EcoGrip Yoga Mat")
    product_desc = st.text_area("Product Description", placeholder="Describe your product...", height=100)
    target_audience = st.text_input("Target Audience", placeholder="e.g. Health-conscious millennials")
    brand_tone = st.selectbox("Brand Tone", options=SUPPORTED_TONES, index=0)
    generate_btn = st.button("Generate Campaign", type="primary", use_container_width=True)

st.divider()
col1, col2 = st.columns([1, 1], gap="large")


def run_pipeline() -> dict[str, Any]:
    """Run the full content generation pipeline with progress indicators."""
    results: dict[str, Any] = {}
    progress_bar = st.progress(0, text="Initialising...")
    steps = [
        (10, "Generating campaign tagline..."),
        (25, "Writing blog introduction..."),
        (40, "Composing social media posts..."),
        (55, "Building image prompt..."),
        (75, "Generating hero image..."),
        (95, "Generating promotional video..."),
    ]

    try:
        progress_bar.progress(steps[0][0], text=steps[0][1])
        tagline = generate_tagline(product=product_name, tone=brand_tone)
        results["tagline"] = tagline

        progress_bar.progress(steps[1][0], text=steps[1][1])
        results["blog"] = generate_blog_intro(
            product=product_name, audience=target_audience,
            tagline=tagline, tone=brand_tone,
        )

        progress_bar.progress(steps[2][0], text=steps[2][1])
        results["social"] = generate_social_posts(
            product=product_name, audience=target_audience, tone=brand_tone,
        )

        progress_bar.progress(steps[3][0], text=steps[3][1])
        results["image_prompt"] = build_image_prompt(product=product_name, tone=brand_tone)

        progress_bar.progress(steps[4][0], text=steps[4][1])
        image_url = generate_image(prompt=results["image_prompt"])
        results["image_url"] = image_url

        if image_url:
            progress_bar.progress(steps[5][0], text=steps[5][1])
            results["video_url"] = generate_video(
                image_url=image_url, tone=brand_tone,
                product=product_name, tagline=tagline,
            )
        else:
            results["video_url"] = ""

        progress_bar.progress(100, text="Campaign complete!")
        time.sleep(0.3)
        progress_bar.empty()

    except Exception as e:
        logger.error("Pipeline error: %s", e)
        progress_bar.empty()
        st.error(f"Pipeline error: {e}")

    return results
if generate_btn:
    if not product_name.strip():
        st.error("Please enter a Product Name.")
    elif not target_audience.strip():
        st.error("Please enter a Target Audience.")
    else:
        with st.spinner("Running campaign pipeline..."):
            results = run_pipeline()
            st.session_state.results = results
            st.session_state.generated = bool(results)
            if results:
                st.success("Campaign generated successfully!")
            else:
                st.warning("Pipeline completed with no results.")

if st.session_state.generated:
    r = st.session_state.results
    with col1:
        if r.get("tagline"):
            st.markdown(f'<div class="card"><h3>Tagline <span class="success-badge">OK</span></h3><p style="font-size:1.3rem;font-weight:500;color:#4263eb;">{r["tagline"]}</p></div>', unsafe_allow_html=True)
        if r.get("blog"):
            st.markdown(f'<div class="card"><h3>Blog Introduction <span class="success-badge">OK</span></h3><p>{r["blog"]}</p></div>', unsafe_allow_html=True)
            st.download_button("Download Blog", data=r["blog"], file_name="blog_introduction.txt", mime="text/plain", key="dl_blog")
        if r.get("social"):
            parts = ""
            labels = {"twitter": "Twitter", "instagram": "Instagram", "linkedin": "LinkedIn"}
            for p, c in r["social"].items():
                parts += f"<p><strong>{labels.get(p, p)}</strong><br>{c}</p><hr style='margin:0.5rem 0;'>"
            st.markdown(f'<div class="card"><h3>Social Media Posts <span class="success-badge">OK</span></h3>{parts}</div>', unsafe_allow_html=True)
            social_json = json.dumps(r["social"], indent=2)
            with st.expander("Raw JSON"):
                st.code(social_json, language="json")
            st.download_button("Download Social Posts (JSON)", data=social_json, file_name="social_posts.json", mime="application/json", key="dl_social")

    with col2:
        if r.get("image_prompt"):
            st.markdown(f'<div class="card"><h3>Image Prompt <span class="success-badge">OK</span></h3><p style="font-size:0.9rem;">{r["image_prompt"]}</p></div>', unsafe_allow_html=True)
        if r.get("image_url"):
            st.markdown(f'<div class="card"><h3>Hero Image <span class="success-badge">OK</span></h3><img src="{r["image_url"]}" alt="Hero" style="width:100%;border-radius:8px;margin-top:0.5rem;" /></div>', unsafe_allow_html=True)
            st.download_button("Download Image URL", data=r["image_url"], file_name="hero_image_url.txt", mime="text/plain", key="dl_image")
        else:
            st.markdown('<div class="card"><h3>Hero Image</h3><p style="color:#868e96;">Image generation skipped or failed. Verify your API keys.</p></div>', unsafe_allow_html=True)
        if r.get("video_url"):
            st.markdown(f'<div class="card"><h3>Promotional Video Concept <span class="success-badge">OK</span></h3><div style="font-size:0.9rem;">{r["video_url"]}</div></div>', unsafe_allow_html=True)
            st.download_button("Download Video Concept", data=r["video_url"], file_name="video_concept.txt", mime="text/plain", key="dl_video")
        else:
            st.markdown('<div class="card"><h3>Promotional Video Concept</h3><p style="color:#868e96;">Video concept generation skipped or failed.</p></div>', unsafe_allow_html=True)

elif not generate_btn:
    with col1:
        for t in ["Campaign Tagline", "Blog Introduction", "Social Media Posts"]:
            st.markdown(f'<div class="card"><h3>{t}</h3><p style="color:#adb5bd;">Fill in the form and click Generate.</p></div>', unsafe_allow_html=True)
    with col2:
        for t in ["Image Prompt", "Hero Image", "Video Concept"]:
            st.markdown(f'<div class="card"><h3>{t}</h3><p style="color:#adb5bd;">Generated content will appear here.</p></div>', unsafe_allow_html=True)

st.divider()
st.markdown('<p style="text-align:center;color:#868e96;font-size:0.85rem;">Built with Streamlit | Powered by OpenRouter | Models: GPT-4o-mini, GPT-5-Image-Mini</p>', unsafe_allow_html=True)