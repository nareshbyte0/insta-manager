/**
 * InstaManager — Modern Instagram Downloader Application Logic
 * In-browser instant downloads, rich media previews, category filtering,
 * and structured ZIP archive generation.
 */

// ─── Application State ────────────────────────────────────────

let state = {
    username: "",
    profile: null,
    items: [],
    selectedShortcodes: new Set(),
    activeFilter: "all",
    filterTypes: ["everything"],
    isFetching: false,
};

// ─── DOM Helpers ──────────────────────────────────────────────

const $ = (id) => document.getElementById(id);
const show = (el) => el && el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

// ─── Toast Notifications ──────────────────────────────────────

function showToast(message, type = "info") {
    const container = $("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    const icon = type === "success" ? "✓" : type === "error" ? "⚠️" : "ℹ️";
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(15px)";
        toast.style.transition = "all 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatNumber(num) {
    if (!num && num !== 0) return "0";
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "K";
    return num.toLocaleString();
}

// ─── Quick Filter Chips ───────────────────────────────────────

function toggleTypeChip(btn) {
    const type = btn.getAttribute("data-type");

    if (type === "everything") {
        document.querySelectorAll(".type-filter-chips .chip").forEach(c => c.classList.remove("active"));
        btn.classList.add("active");
        state.filterTypes = ["everything"];
    } else {
        const everythingChip = document.querySelector('.type-filter-chips [data-type="everything"]');
        if (everythingChip) everythingChip.classList.remove("active");

        if (btn.classList.contains("active")) {
            btn.classList.remove("active");
            state.filterTypes = state.filterTypes.filter(t => t !== type);
            if (state.filterTypes.length === 0) {
                if (everythingChip) everythingChip.classList.add("active");
                state.filterTypes = ["everything"];
            }
        } else {
            btn.classList.add("active");
            state.filterTypes.push(type);
        }
    }
}

function setSearchUsername(username) {
    const input = $("username-input");
    input.value = username;
    handleSearch(new Event("submit"));
}

// ─── Main Search & Fetch Flow ─────────────────────────────────

async function handleSearch(event) {
    if (event) event.preventDefault();

    const input = $("username-input");
    const rawUser = input.value.trim();

    if (!rawUser) {
        showToast("Please enter an Instagram username or profile link", "error");
        return;
    }

    if (state.isFetching) return;

    state.isFetching = true;
    const fetchBtn = $("btn-fetch");
    fetchBtn.disabled = true;
    fetchBtn.innerHTML = `<span class="spinner-ring" style="width:18px;height:18px;border-width:2.5px;"></span> <span>Fetching...</span>`;

    hide($("error-section"));
    hide($("dashboard-section"));
    show($("loading-section"));

    $("loading-subtitle").textContent = `Connecting to Instagram CDN for @${rawUser.replace('@', '')}...`;

    try {
        const res = await fetch("/api/fetch-profile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: rawUser,
                limit: 36,
                content_types: state.filterTypes,
            }),
        });

        const data = await res.json();

        if (!res.ok || !data.success) {
            showError(data.error || "Unable to load Instagram profile");
            return;
        }

        // Check if private
        if (data.is_private) {
            showError(`Account @${data.profile.username} is private. Instagram only allows downloading media from public accounts.`);
            return;
        }

        state.username = data.profile.username;
        state.profile = data.profile;
        state.items = data.items || [];
        state.activeFilter = "all";

        // Select all items by default for 1-click bulk ZIP download
        state.selectedShortcodes = new Set(state.items.map(i => i.shortcode));

        renderDashboard(data);
        showToast(`Loaded ${state.items.length} media items for @${state.username}! ✨`, "success");

    } catch (err) {
        showError("Network error. Please make sure the InstaManager server is running.");
    } finally {
        state.isFetching = false;
        fetchBtn.disabled = false;
        fetchBtn.innerHTML = `
            <span class="btn-text">Load Media</span>
            <svg class="btn-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
        `;
        hide($("loading-section"));
    }
}

function showError(msg) {
    hide($("loading-section"));
    hide($("dashboard-section"));
    show($("error-section"));
    $("error-desc").textContent = msg;
}

function hideError() {
    hide($("error-section"));
    $("username-input").focus();
}

// ─── Dashboard Rendering ──────────────────────────────────────

function renderDashboard(data) {
    const p = data.profile;

    // 1. Profile Card
    const avatarEl = $("profile-avatar");
    const rawPic = p.profile_pic_url || "";
    avatarEl.src = rawPic.startsWith("http") ? `/api/proxy-media?url=${encodeURIComponent(rawPic)}` : rawPic;
    avatarEl.onerror = function() {
        this.onerror = null;
        this.src = rawPic || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=300&q=80";
    };
    $("profile-fullname").textContent = p.full_name || p.username;
    $("profile-handle").textContent = `@${p.username}`;
    $("profile-bio").textContent = p.biography || "No bio available.";

    if (p.is_verified) {
        show($("verified-badge"));
    } else {
        hide($("verified-badge"));
    }

    if (p.external_url) {
        const linkEl = $("profile-link");
        linkEl.href = p.external_url;
        linkEl.textContent = p.external_url;
        show(linkEl);
    } else {
        hide($("profile-link"));
    }

    $("stat-posts-count").textContent = formatNumber(p.media_count);
    $("stat-followers").textContent = formatNumber(p.followers);
    $("stat-following").textContent = formatNumber(p.followees);

    // 2. Tab Counts
    const counts = data.counts || {};
    $("count-all").textContent = counts.all || state.items.length;
    $("count-photos").textContent = counts.photos || 0;
    $("count-videos").textContent = counts.videos || 0;
    $("count-reels").textContent = counts.reels || 0;
    $("count-carousels").textContent = counts.carousels || 0;

    // Reset Tab Selection
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === "all");
    });

    // 3. Render Cards
    renderMediaCards();
    updateSelectionUI();

    show($("dashboard-section"));

    // Smooth scroll to dashboard
    $("dashboard-section").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ─── Media Cards Rendering ────────────────────────────────────

function renderMediaCards() {
    const grid = $("media-grid");
    grid.innerHTML = "";

    const filteredItems = state.activeFilter === "all"
        ? state.items
        : state.items.filter(item => item.type === state.activeFilter);

    if (filteredItems.length === 0) {
        show($("empty-gallery"));
        return;
    } else {
        hide($("empty-gallery"));
    }

    filteredItems.forEach(item => {
        const card = createMediaCard(item);
        grid.appendChild(card);
    });
}

function createMediaCard(item) {
    const isSelected = state.selectedShortcodes.has(item.shortcode);
    const card = document.createElement("div");
    card.className = `media-card ${isSelected ? "selected" : ""}`;
    card.id = `card-${item.shortcode}`;

    // Badge styling & icon
    const badgeInfo = {
        reels: { label: "Reel 🎞️", cls: "badge-reels" },
        videos: { label: "Video 🎬", cls: "badge-videos" },
        photos: { label: "Photo 🖼️", cls: "badge-photos" },
        carousels: { label: `Carousel (${item.slides ? item.slides.length : "Multi"}) 📸`, cls: "badge-carousels" },
    }[item.type] || { label: "Media 📸", cls: "badge-photos" };

    // Duration or extra badge
    let durationBadge = "";
    if (item.video_duration) {
        const mins = Math.floor(item.video_duration / 60);
        const secs = Math.floor(item.video_duration % 60);
        durationBadge = `<span class="duration-badge">${mins}:${secs < 10 ? "0" : ""}${secs}</span>`;
    }

    // Carousel slides pills
    let slidesHtml = "";
    if (item.type === "carousels" && item.slides && item.slides.length > 1) {
        slidesHtml = `
            <div class="carousel-slides-tray">
                ${item.slides.map((s, idx) => `
                    <button type="button" class="slide-pill ${idx === 0 ? 'active' : ''}" 
                        onclick="switchCarouselSlide('${item.shortcode}', ${idx}, event)">
                        Slide ${s.index} ${s.is_video ? '🎥' : '📷'}
                    </button>
                `).join('')}
            </div>
        `;
    }

    const downloadExt = item.is_video ? "mp4" : "jpg";
    const downloadFilename = `@${state.username}_${item.type}_${item.shortcode}.${downloadExt}`;
    const targetMediaUrl = item.is_video ? item.video_url : item.display_url;
    const thumbSrc = item.display_url && item.display_url.startsWith("http")
        ? `/api/proxy-media?url=${encodeURIComponent(item.display_url)}`
        : item.display_url;

    card.innerHTML = `
        <div class="card-media-wrapper" onclick="previewMedia('${item.shortcode}')">
            <img class="card-thumb" id="thumb-${item.shortcode}" referrerpolicy="no-referrer" src="${thumbSrc}" onerror="this.onerror=null; this.src='${item.display_url}'" alt="Instagram Media" loading="lazy">
            
            <div class="card-select-overlay" onclick="event.stopPropagation()">
                <label>
                    <input type="checkbox" class="card-checkbox" 
                        ${isSelected ? "checked" : ""} 
                        onchange="toggleCardSelect('${item.shortcode}', this.checked)">
                    <span class="card-custom-check"></span>
                </label>
            </div>

            <div class="card-badge ${badgeInfo.cls}">${badgeInfo.label}</div>

            ${item.is_video ? `
                <div class="card-hover-play">
                    <div class="play-circle">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                    </div>
                </div>
            ` : ''}
        </div>

        <div class="card-body">
            <div class="card-meta-row">
                <span class="card-date">${item.date || "Recent"}</span>
                <div class="card-stats">
                    ${item.likes ? `<span>❤️ ${formatNumber(item.likes)}</span>` : ""}
                    ${item.comments ? `<span>💬 ${formatNumber(item.comments)}</span>` : ""}
                </div>
            </div>

            ${slidesHtml}

            <p class="card-caption" title="${escapeHtml(item.caption)}">
                ${escapeHtml(item.caption) || "Instagram post"}
            </p>

            <div class="card-actions">
                <button type="button" class="btn-card-download" 
                    id="btn-dl-${item.shortcode}"
                    onclick="downloadSingleItem('${item.shortcode}', '${encodeURIComponent(targetMediaUrl)}', '${downloadFilename}', event)">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    <span>Download</span>
                </button>

                <button type="button" class="btn-card-preview" title="Full Preview" 
                    onclick="previewMedia('${item.shortcode}')">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
                </button>
            </div>
        </div>
    `;

    return card;
}

// ─── Carousel Slide Switching ─────────────────────────────────

function switchCarouselSlide(shortcode, slideIdx, event) {
    if (event) event.stopPropagation();

    const item = state.items.find(i => i.shortcode === shortcode);
    if (!item || !item.slides || !item.slides[slideIdx]) return;

    const slide = item.slides[slideIdx];
    const thumb = $(`thumb-${shortcode}`);
    if (thumb) thumb.src = slide.display_url;

    // Update active pill
    const card = $(`card-${shortcode}`);
    if (card) {
        card.querySelectorAll(".slide-pill").forEach((p, idx) => {
            p.classList.toggle("active", idx === slideIdx);
        });

        // Update target download button URL and filename
        const btnDl = $(`btn-dl-${shortcode}`);
        if (btnDl) {
            const ext = slide.is_video ? "mp4" : "jpg";
            const filename = `@${state.username}_carousel_${shortcode}_slide${slide.index}.${ext}`;
            const targetUrl = slide.is_video ? slide.video_url : slide.display_url;
            btnDl.setAttribute("onclick", `downloadSingleItem('${shortcode}', '${encodeURIComponent(targetUrl)}', '${filename}', event)`);
        }
    }
}

// ─── Filtering Tabs ───────────────────────────────────────────

function filterGallery(tabName) {
    state.activeFilter = tabName;

    document.querySelectorAll(".filter-tabs .tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === tabName);
    });

    renderMediaCards();
    updateSelectionUI();
}

// ─── Selection Management ─────────────────────────────────────

function toggleCardSelect(shortcode, isChecked) {
    if (isChecked) {
        state.selectedShortcodes.add(shortcode);
    } else {
        state.selectedShortcodes.delete(shortcode);
    }

    const card = $(`card-${shortcode}`);
    if (card) card.classList.toggle("selected", isChecked);

    updateSelectionUI();
}

function toggleSelectAll(isChecked) {
    const currentList = state.activeFilter === "all"
        ? state.items
        : state.items.filter(i => i.type === state.activeFilter);

    currentList.forEach(item => {
        if (isChecked) {
            state.selectedShortcodes.add(item.shortcode);
        } else {
            state.selectedShortcodes.delete(item.shortcode);
        }
    });

    renderMediaCards();
    updateSelectionUI();
}

function updateSelectionUI() {
    const totalLoaded = state.items.length;
    const selectedCount = state.selectedShortcodes.size;

    $("select-count-text").textContent = `Select All (${selectedCount} / ${totalLoaded} selected)`;
    $("select-all-checkbox").checked = selectedCount > 0 && selectedCount === totalLoaded;

    const btnSelected = $("btn-download-selected");
    if (selectedCount > 0) {
        show(btnSelected);
        $("selected-btn-text").textContent = `Download Selected (${selectedCount} ZIP)`;
    } else {
        hide(btnSelected);
    }
}

// ─── Individual Download Flow ─────────────────────────────────

function downloadSingleItem(shortcode, encodedUrl, filename, event) {
    if (event) event.stopPropagation();

    const mediaUrl = decodeURIComponent(encodedUrl);
    showToast(`Downloading ${filename}...`, "info");

    // Direct browser trigger via streaming endpoint
    const downloadUri = `/api/download-file?url=${encodeURIComponent(mediaUrl)}&filename=${encodeURIComponent(filename)}`;
    
    // Create temporary link and click
    const a = document.createElement("a");
    a.href = downloadUri;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => a.remove(), 200);
}

function downloadAvatar() {
    if (!state.profile || !state.profile.profile_pic_url) return;
    const filename = `@${state.username}_profile_pic.jpg`;
    downloadSingleItem("avatar", encodeURIComponent(state.profile.profile_pic_url), filename);
}

function exportProfileJson() {
    if (!state.profile) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(state.profile, null, 2));
    const a = document.createElement("a");
    a.href = dataStr;
    a.download = `@${state.username}_profile_info.json`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => a.remove(), 200);
    showToast("Exported profile info as JSON", "success");
}

// ─── Bulk ZIP Downloads ───────────────────────────────────────

async function downloadAllZip() {
    if (state.items.length === 0) {
        showToast("No items to download", "error");
        return;
    }

    await triggerZipDownload(state.items, `@${state.username}_all_instagram.zip`);
}

async function downloadSelectedZip() {
    const selectedItems = state.items.filter(i => state.selectedShortcodes.has(i.shortcode));
    if (selectedItems.length === 0) {
        showToast("Please select at least 1 item", "error");
        return;
    }

    await triggerZipDownload(selectedItems, `@${state.username}_selected_${selectedItems.length}.zip`);
}

async function triggerZipDownload(itemsToZip, zipFilename) {
    const zipBtn = $("btn-zip-all");
    const origHtml = zipBtn.innerHTML;
    zipBtn.disabled = true;
    zipBtn.innerHTML = `<span class="spinner-ring" style="width:16px;height:16px;border-width:2px;"></span> <span>Packing ZIP...</span>`;

    showToast("Generating organized ZIP archive... This may take a few seconds.", "info");

    try {
        const res = await fetch("/api/download-zip", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: state.username,
                profile: state.profile,
                items: itemsToZip,
            }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || "ZIP generation failed");
        }

        // Receive Blob and trigger download
        const blob = await res.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = zipFilename;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            a.remove();
            window.URL.revokeObjectURL(blobUrl);
        }, 500);

        showToast("ZIP Archive downloaded successfully! 🎉", "success");

    } catch (err) {
        showToast(`ZIP Download Error: ${err.message}`, "error");
    } finally {
        zipBtn.disabled = false;
        zipBtn.innerHTML = origHtml;
    }
}

// ─── Save to Local PC Folder ──────────────────────────────────

async function saveToDisk() {
    if (state.items.length === 0) return;

    showToast("Saving files to local downloads folder...", "info");

    try {
        const res = await fetch("/api/save-to-folder", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: state.username,
                profile: state.profile,
                items: state.items,
            }),
        });

        const data = await res.json();
        if (data.success) {
            showToast(data.message, "success");
            // Ask user if they want to open the folder
            setTimeout(() => {
                fetch(`/api/open-folder/${state.username}`);
            }, 800);
        } else {
            showToast(data.error || "Could not save to folder", "error");
        }
    } catch (err) {
        showToast("Error saving to folder", "error");
    }
}

// ─── Lightbox / Preview Modal ─────────────────────────────────

function previewMedia(shortcode) {
    const item = state.items.find(i => i.shortcode === shortcode);
    if (!item) return;

    const modal = $("preview-modal");
    const wrapper = $("modal-media-wrapper");
    wrapper.innerHTML = "";

    const ext = item.is_video ? "mp4" : "jpg";
    const filename = `@${state.username}_${item.type}_${item.shortcode}.${ext}`;
    const mediaUrl = item.is_video ? item.video_url : item.display_url;

    if (item.is_video) {
        const video = document.createElement("video");
        video.src = `/api/proxy-media?url=${encodeURIComponent(item.video_url)}`;
        video.controls = true;
        video.autoplay = true;
        video.playsInline = true;
        wrapper.appendChild(video);
    } else {
        const img = document.createElement("img");
        img.src = item.display_url;
        img.alt = "Instagram Full Preview";
        wrapper.appendChild(img);
    }

    $("modal-type-badge").textContent = `${item.type.toUpperCase()}`;
    $("modal-date").textContent = item.date || "Instagram Post";
    $("modal-caption").textContent = item.caption || "No caption provided.";
    $("modal-stats").innerHTML = `❤️ ${formatNumber(item.likes || 0)} &nbsp;&bull;&nbsp; 💬 ${formatNumber(item.comments || 0)}`;

    const dlBtn = $("btn-modal-download");
    dlBtn.onclick = (e) => downloadSingleItem(item.shortcode, encodeURIComponent(mediaUrl), filename, e);

    show(modal);
}

function closePreviewModal(event) {
    if (event && event.target && event.target.closest && event.target.closest(".modal-content")) {
        return;
    }
    const modal = $("preview-modal");
    // Pause any playing video
    const video = modal.querySelector("video");
    if (video) video.pause();
    hide(modal);
}

// Close modal on Escape key
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        closePreviewModal();
    }
});
