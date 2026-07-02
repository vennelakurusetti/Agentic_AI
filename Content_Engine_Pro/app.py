"""
app.py — Content Engine Pro (Streamlit)

Extends the original AI Content Engine with:
1. AI Self-Critique Loop (PASS/FAIL cards, auto-regeneration)
2. Voiceover Generation (TTS with audio player + download)
3. Multi-Channel Adaptation (B2B LinkedIn, Gen-Z TikTok, Parents Facebook)

Preserves all original functionality: tagline, blog, social, image, video.
"""

import json
import logging
import time
from typing import Any

import streamlit as st

from config import CHANNEL_OPTIONS, SUPPORTED_TONES
from text_gen import generate_tagline, generate_blog_intro, generate_social_posts
from image_gen import build_image_prompt, generate_image
from video_gen import generate_video
from critic import run_self_critique, CriticReport
from voiceover_gen import generate_voiceover
from adapter import adapt_for_channel, AdaptationResult

# ── Logging ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Page Config ──────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Content Engine Pro",
    page_icon=":sparkles:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ──────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .card { background: white; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid #e9ecef; }
    .card h3 { margin-top: 0; color: #212529; font-weight: 600; }
    .card p, .card div { color: #495057; }
    .success-badge { display: inline-block; background: #d3f9d8; color: #2b8a3e; padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-left: 0.5rem; }
    .fail-badge { display: inline-block; background: #ffe3e3; color: #c92a2a; padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-left: 0.5rem; }
    .pass-card { border-left: 4px solid #2b8a3e; background: #f0fff4; }
    .fail-card { border-left: 4px solid #c92a2a; background: #fff5f5; }
    .stButton>button { background: #4263eb; color: white; border-radius: 8px; padding: 0.5rem 2rem; font-weight: 600; border: none; }
    .stButton>button:hover { background: #3b5bdb; }
    hr { margin: 2rem 0; }
    .section-header { margin-top: 2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #4263eb; }
    .reused-badge { display: inline-block; background: #e7f5ff; color: #1971c2; padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
</style>""", unsafe_allow_html=True)

# ── Title ────────────────────────────────────────────────────────────────

st.title(":sparkles: Content Engine Pro")
st.markdown(
    '<p style="color: #868e96; margin-top: -0.5rem;">'
    "Generate campaign taglines, blog intros, social posts, hero images, "
    "promotional videos — with self-critique, voiceover, and multi-channel adaptation."
    '</p>',
    unsafe_allow_html=True,
)

# ── Session State ────────────────────────────────────────────────────────

if "generated" not in st.session_state:
    st.session_state.generated = False
    st.session_state.results: dict[str, Any] = {}
    st.session_state.critic_report: CriticReport | None = None
    st.session_state.voiceover_script: str | None = None
    st.session_state.voiceover_audio: bytes | None = None
    st.session_state.adaptations: dict[str, AdaptationResult] = {}
    st.session_state.selected_channel: str | None = None

# ── Sidebar ──────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Campaign Brief")
    product_name = st.text_input("Product Name", placeholder="e.g. EcoGrip Yoga Mat")
    product_desc = st.text_area(
        "Product Description", placeholder="Describe your product...", height=100,
    )
    target_audience = st.text_input(
        "Target Audience", placeholder="e.g. Health-conscious millennials",
    )
    brand_tone = st.selectbox("Brand Tone", options=SUPPORTED_TONES, index=0)
    generate_btn = st.button("Generate Campaign", type="primary", use_container_width=True)


# ── Pipeline ─────────────────────────────────────────────────────────────


def run_pipeline() -> dict[str, Any]:
    """Run the full content generation pipeline with progress indicators.

    Returns:
        Dict containing all generated assets.
    """
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
        results["image_prompt"] = build_image_prompt(
            product=product_name, tone=brand_tone,
        )

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


# ── Generate Button Handler ──────────────────────────────────────────────

if generate_btn:
    if not product_name.strip():
        st.error("Please enter a Product Name.")
    elif not target_audience.strip():
        st.error("Please enter a Target Audience.")
    else:
        with st.spinner("Running campaign pipeline..."):
            # Step 1-6: Original pipeline
            results = run_pipeline()
            st.session_state.results = results
            st.session_state.generated = bool(results)

            if results:
                # Step 7: Self-Critique
                st.info("Running self-critique evaluation...")
                try:
                    final_assets, critic_report = run_self_critique(
                        product=product_name,
                        audience=target_audience,
                        tone=brand_tone,
                        tagline=results.get("tagline", ""),
                        blog=results.get("blog", ""),
                        social=results.get("social", {}),
                    )
                    # Update results with potentially regenerated assets
                    results["tagline"] = final_assets["tagline"]
                    results["blog"] = final_assets["blog"]
                    results["social"] = final_assets["social"]
                    st.session_state.critic_report = critic_report
                except Exception as e:
                    logger.error("Self-critique failed: %s", e)
                    st.warning(f"Self-critique encountered an error: {e}")
                    st.session_state.critic_report = None

                # Step 8: Voiceover Generation
                if results.get("blog"):
                    st.info("Generating voiceover...")
                    try:
                        script, audio = generate_voiceover(results["blog"])
                        st.session_state.voiceover_script = script
                        st.session_state.voiceover_audio = audio
                    except Exception as e:
                        logger.error("Voiceover generation failed: %s", e)
                        st.warning(f"Voiceover generation encountered an error: {e}")
                        st.session_state.voiceover_script = None
                        st.session_state.voiceover_audio = None

                # Step 9: Pre-compute adaptations
                st.session_state.adaptations = {}
                st.session_state.selected_channel = None

                st.success("Campaign generated successfully!")
            else:
                st.warning("Pipeline completed with no results.")


# ── Display Generated Campaign ──────────────────────────────────────────

if st.session_state.generated:
    r = st.session_state.results

    # ── Original Campaign Display ──────────────────────────────────────
    st.markdown("## Generated Campaign")
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        if r.get("tagline"):
            st.markdown(
                f'<div class="card"><h3>Tagline <span class="success-badge">OK</span></h3>'
                f'<p style="font-size:1.3rem;font-weight:500;color:#4263eb;">{r["tagline"]}</p></div>',
                unsafe_allow_html=True,
            )
        if r.get("blog"):
            st.markdown(
                f'<div class="card"><h3>Blog Introduction <span class="success-badge">OK</span></h3>'
                f'<p>{r["blog"]}</p></div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "Download Blog", data=r["blog"],
                file_name="blog_introduction.txt", mime="text/plain", key="dl_blog",
            )
        if r.get("social"):
            parts = ""
            labels = {"twitter": "Twitter", "instagram": "Instagram", "linkedin": "LinkedIn"}
            for p, c in r["social"].items():
                parts += (
                    f"<p><strong>{labels.get(p, p)}</strong><br>{c}</p>"
                    f"<hr style='margin:0.5rem 0;'>"
                )
            st.markdown(
                f'<div class="card"><h3>Social Media Posts <span class="success-badge">OK</span></h3>'
                f'{parts}</div>',
                unsafe_allow_html=True,
            )
            social_json = json.dumps(r["social"], indent=2)
            with st.expander("Raw JSON"):
                st.code(social_json, language="json")
            st.download_button(
                "Download Social Posts (JSON)", data=social_json,
                file_name="social_posts.json", mime="application/json", key="dl_social",
            )

    with col2:
        if r.get("image_prompt"):
            st.markdown(
                f'<div class="card"><h3>Image Prompt <span class="success-badge">OK</span></h3>'
                f'<p style="font-size:0.9rem;">{r["image_prompt"]}</p></div>',
                unsafe_allow_html=True,
            )
        if r.get("image_url"):
            st.markdown(
                f'<div class="card"><h3>Hero Image <span class="success-badge">OK</span></h3>'
                f'<img src="{r["image_url"]}" alt="Hero" style="width:100%;border-radius:8px;margin-top:0.5rem;" />'
                f'<p style="margin-top:0.5rem;"><span class="reused-badge">Reused from original campaign</span></p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "Download Image URL", data=r["image_url"],
                file_name="hero_image_url.txt", mime="text/plain", key="dl_image",
            )
        else:
            st.markdown(
                '<div class="card"><h3>Hero Image</h3>'
                '<p style="color:#868e96;">Image generation skipped or failed. Verify your API keys.</p></div>',
                unsafe_allow_html=True,
            )
        if r.get("video_url"):
            st.markdown(
                f'<div class="card"><h3>Promotional Video Concept <span class="success-badge">OK</span></h3>'
                f'<div style="font-size:0.9rem;">{r["video_url"]}</div>'
                f'<p style="margin-top:0.5rem;"><span class="reused-badge">Reused from original campaign</span></p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "Download Video Concept", data=r["video_url"],
                file_name="video_concept.txt", mime="text/plain", key="dl_video",
            )
        else:
            st.markdown(
                '<div class="card"><h3>Promotional Video Concept</h3>'
                '<p style="color:#868e96;">Video concept generation skipped or failed.</p></div>',
                unsafe_allow_html=True,
            )

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 1: Self-Critique Report
    # ═══════════════════════════════════════════════════════════════════
    st.markdown('<h2 class="section-header">1. Self-Critique Report</h2>', unsafe_allow_html=True)

    critic_report = st.session_state.get("critic_report")
    if critic_report:
        # Display PASS/FAIL cards
        crit_cols = st.columns(3)
        asset_labels = {
            "tagline": "Tagline",
            "blog": "Blog Introduction",
            "social": "Social Posts",
        }

        for idx, (asset_name, result) in enumerate(critic_report.results.items()):
            with crit_cols[idx]:
                if result.passed:
                    st.markdown(
                        f'<div class="card pass-card">'
                        f'<h3>{asset_labels.get(asset_name, asset_name)} <span class="success-badge">PASS</span></h3>'
                        f'<p style="color:#2b8a3e;">✓ No issues found</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    issue_text = result.issue or "Unknown issue"
                    retry_info = ""
                    if result.retries_used >= 2:
                        retry_info = (
                            '<p style="color:#c92a2a;font-weight:600;">'
                            '⚠ Failed after 2 retries</p>'
                        )
                    elif result.retries_used > 0:
                        retry_info = (
                            f'<p style="color:#e67700;">'
                            f'Regenerated ({result.retries_used} retries)</p>'
                        )

                    st.markdown(
                        f'<div class="card fail-card">'
                        f'<h3>{asset_labels.get(asset_name, asset_name)} <span class="fail-badge">FAIL</span></h3>'
                        f'<p style="color:#c92a2a;">{issue_text}</p>'
                        f'{retry_info}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        # Retry history expander
        has_retries = any(
            result.retry_history for result in critic_report.results.values()
        )
        if has_retries:
            with st.expander("Retry History"):
                for asset_name, result in critic_report.results.items():
                    if result.retry_history:
                        st.markdown(f"**{asset_labels.get(asset_name, asset_name)}**")
                        for entry in result.retry_history:
                            st.markdown(f"- {entry}")
    else:
        st.info("Self-critique was not run or encountered an error.")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 2: Voiceover
    # ═══════════════════════════════════════════════════════════════════
    st.markdown('<h2 class="section-header">2. Voiceover</h2>', unsafe_allow_html=True)

    voiceover_script = st.session_state.get("voiceover_script")
    voiceover_audio = st.session_state.get("voiceover_audio")

    if voiceover_script:
        st.markdown(
            f'<div class="card"><h3>Narration Script</h3>'
            f'<p style="font-style:italic;">{voiceover_script}</p></div>',
            unsafe_allow_html=True,
        )

        if voiceover_audio:
            # Audio player
            st.audio(voiceover_audio, format="audio/mp3")

            # Download button
            st.download_button(
                label="Download Voiceover (MP3)",
                data=voiceover_audio,
                file_name="voiceover.mp3",
                mime="audio/mpeg",
                key="dl_voiceover",
            )
        else:
            st.warning(
                "Voiceover script was generated but TTS audio generation failed. "
                "Check your API key has access to TTS models."
            )
    else:
        st.info("Voiceover generation was skipped or failed.")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 3: Channel Adaptation
    # ═══════════════════════════════════════════════════════════════════
    st.markdown('<h2 class="section-header">3. Channel Adaptation</h2>', unsafe_allow_html=True)

    adapt_col1, adapt_col2 = st.columns([2, 1])
    with adapt_col1:
        selected_channel = st.selectbox(
            "Adapt Campaign For",
            options=[""] + CHANNEL_OPTIONS,
            key="channel_select",
        )
    with adapt_col2:
        adapt_btn = st.button(
            "Adapt Campaign",
            type="primary",
            use_container_width=True,
            disabled=not selected_channel,
        )

    if adapt_btn and selected_channel:
        with st.spinner(f"Adapting campaign for {selected_channel}..."):
            try:
                result = adapt_for_channel(
                    channel=selected_channel,
                    tagline=r.get("tagline", ""),
                    blog=r.get("blog", ""),
                    social=r.get("social", {}),
                )
                if result:
                    st.session_state.adaptations[selected_channel] = result
                    st.session_state.selected_channel = selected_channel
                    st.success(f"Campaign adapted for {selected_channel}!")
                else:
                    st.error(f"Adaptation for {selected_channel} failed.")
            except Exception as e:
                logger.error("Adaptation error: %s", e)
                st.error(f"Adaptation error: {e}")

    # Display adapted assets if available
    if st.session_state.selected_channel and st.session_state.adaptations:
        channel = st.session_state.selected_channel
        adapted = st.session_state.adaptations.get(channel)

        if adapted:
            st.markdown(
                f'<div class="card">'
                f'<h3>Adapted for {channel} <span class="success-badge">OK</span></h3>'
                f'</div>',
                unsafe_allow_html=True,
            )

            adapted_tabs = st.tabs(["Tagline", "Blog", "Social Posts"])

            with adapted_tabs[0]:
                st.markdown(
                    f'<div class="card">'
                    f'<h4>Adapted Tagline</h4>'
                    f'<p style="font-size:1.2rem;font-weight:500;color:#4263eb;">'
                    f'{adapted.tagline}</p></div>',
                    unsafe_allow_html=True,
                )

            with adapted_tabs[1]:
                st.markdown(
                    f'<div class="card"><h4>Adapted Blog</h4>'
                    f'<p>{adapted.blog}</p></div>',
                    unsafe_allow_html=True,
                )

            with adapted_tabs[2]:
                st.markdown(
                    f'<div class="card"><h4>Adapted Social Posts</h4>'
                    f'<p>{adapted.social}</p></div>',
                    unsafe_allow_html=True,
                )

            # Download adapted assets
            adapted_json = json.dumps(adapted.to_dict(), indent=2)
            st.download_button(
                label=f"Download Adapted Assets ({channel})",
                data=adapted_json,
                file_name=f"adapted_{channel.replace(' ', '_').lower()}.json",
                mime="application/json",
                key="dl_adapted",
            )

elif not generate_btn:
    # ── Placeholder Display ────────────────────────────────────────────
    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        for t in ["Campaign Tagline", "Blog Introduction", "Social Media Posts"]:
            st.markdown(
                f'<div class="card"><h3>{t}</h3>'
                f'<p style="color:#adb5bd;">Fill in the form and click Generate.</p></div>',
                unsafe_allow_html=True,
            )
    with col2:
        for t in ["Image Prompt", "Hero Image", "Video Concept"]:
            st.markdown(
                f'<div class="card"><h3>{t}</h3>'
                f'<p style="color:#adb5bd;">Generated content will appear here.</p></div>',
                unsafe_allow_html=True,
            )

# ── Footer ──────────────────────────────────────────────────────────────

st.divider()
st.markdown(
    '<p style="text-align:center;color:#868e96;font-size:0.85rem;">'
    "Built with Streamlit | Powered by OpenRouter | Models: DeepSeek Flash"
    "</p>",
    unsafe_allow_html=True,
)