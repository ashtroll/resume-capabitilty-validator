/**
 * True Capability Validator — Frontend Logic v2
 *
 * Handles:
 *  - Drag-and-drop file upload
 *  - Resume upload via fetch API
 *  - Analysis progress polling
 *  - Redirect to report on completion
 *  - Particle canvas background
 */

document.addEventListener("DOMContentLoaded", () => {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const browseBtn = document.getElementById("browse-btn");
    const fileSelected = document.getElementById("file-selected");
    const fileName = document.getElementById("file-name");
    const removeFile = document.getElementById("remove-file");
    const analyzeBtn = document.getElementById("analyze-btn");
    const uploadSection = document.getElementById("upload-section");
    const progressSection = document.getElementById("progress-section");
    const progressBar = document.getElementById("progress-bar");
    const progressStatus = document.getElementById("progress-status");

    // Guard: only run on the index page
    if (!dropZone) return;

    let selectedFile = null;

    // ── Particle Canvas ─────────────────────────────────────────────────
    initParticles();

    function initParticles() {
        const canvas = document.getElementById("particle-canvas");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        let W = canvas.width = window.innerWidth;
        let H = canvas.height = window.innerHeight;

        window.addEventListener("resize", () => {
            W = canvas.width = window.innerWidth;
            H = canvas.height = window.innerHeight;
        });

        const PARTICLE_COUNT = 55;
        const particles = Array.from({ length: PARTICLE_COUNT }, () => ({
            x: Math.random() * W,
            y: Math.random() * H,
            r: Math.random() * 1.6 + 0.4,
            dx: (Math.random() - 0.5) * 0.35,
            dy: (Math.random() - 0.5) * 0.35,
            o: Math.random() * 0.5 + 0.15,
        }));

        function draw() {
            ctx.clearRect(0, 0, W, H);
            particles.forEach(p => {
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(129, 140, 248, ${p.o})`;
                ctx.fill();

                p.x += p.dx;
                p.y += p.dy;
                if (p.x < 0 || p.x > W) p.dx *= -1;
                if (p.y < 0 || p.y > H) p.dy *= -1;
            });
            requestAnimationFrame(draw);
        }
        draw();
    }

    // ── Drag & Drop ────────────────────────────────────────────────────

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFileSelection(files[0]);
    });

    // ── File Browse ────────────────────────────────────────────────────

    dropZone.addEventListener("click", () => fileInput.click());
    browseBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) handleFileSelection(e.target.files[0]);
    });

    // ── Remove File ────────────────────────────────────────────────────

    removeFile.addEventListener("click", () => {
        selectedFile = null;
        fileInput.value = "";
        dropZone.style.display = "flex";
        fileSelected.style.display = "none";
    });

    // ── Analyze Button ─────────────────────────────────────────────────

    analyzeBtn.addEventListener("click", () => {
        if (selectedFile) uploadAndAnalyze(selectedFile);
    });

    // ── Helpers ─────────────────────────────────────────────────────────

    function handleFileSelection(file) {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            showToast("Please select a PDF file", "error");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showToast("File too large. Maximum size is 10MB.", "error");
            return;
        }
        selectedFile = file;
        fileName.textContent = file.name;
        dropZone.style.display = "none";
        fileSelected.style.display = "flex";
    }

    async function uploadAndAnalyze(file) {
        uploadSection.style.display = "none";
        progressSection.style.display = "block";
        progressBar.style.width = "5%";
        progressStatus.textContent = "Uploading resume...";

        try {
            const formData = new FormData();
            formData.append("file", file);

            const uploadResponse = await fetch("/api/upload", {
                method: "POST",
                body: formData,
            });

            if (!uploadResponse.ok) {
                const err = await uploadResponse.json();
                throw new Error(err.detail || "Upload failed");
            }

            const { job_id } = await uploadResponse.json();
            progressBar.style.width = "15%";
            progressStatus.textContent = "Upload complete. Starting analysis...";

            pollJobStatus(job_id);

        } catch (error) {
            progressStatus.textContent = `Error: ${error.message}`;
            progressBar.style.width = "100%";
            progressBar.style.background = "#ef4444";
        }
    }

    async function pollJobStatus(jobId) {
        const statusMap = {
            pending: { progress: 10, text: "Queued for processing...", step: null },
            parsing: { progress: 25, text: "Parsing PDF document...", step: "step-parsing" },
            extracting: { progress: 40, text: "Extracting entities and profile links...", step: "step-extracting" },
            scraping: { progress: 55, text: "Scraping external profiles...", step: "step-scraping" },
            searching: { progress: 70, text: "Searching the web for digital footprint...", step: "step-searching" },
            analyzing: { progress: 85, text: "Cross-referencing and generating report...", step: "step-analyzing" },
            completed: { progress: 100, text: "Analysis complete! Loading report...", step: "step-completed" },
            failed: { progress: 0, text: "Analysis failed.", step: null },
        };

        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${jobId}`);
                const data = await response.json();
                const status = data.status;
                const info = statusMap[status] || statusMap.pending;

                progressBar.style.width = `${info.progress}%`;
                progressStatus.textContent = info.text;

                updatePipelineSteps(status, statusMap);

                if (status === "completed") {
                    clearInterval(interval);
                    setTimeout(() => {
                        window.location.href = `/api/report/${jobId}/view`;
                    }, 1200);
                } else if (status === "failed") {
                    clearInterval(interval);
                    progressBar.style.background = "#ef4444";
                    progressStatus.textContent = `Analysis failed: ${data.error || "Unknown error"}`;
                }
            } catch (error) {
                console.error("Polling error:", error);
            }
        }, 1500);
    }

    function updatePipelineSteps(currentStatus, statusMap) {
        const order = ["parsing", "extracting", "scraping", "searching", "analyzing", "completed"];
        const currentIndex = order.indexOf(currentStatus);

        order.forEach((status, index) => {
            const stepEl = document.getElementById(`step-${status}`);
            if (!stepEl) return;

            stepEl.classList.remove("active", "completed");

            if (index < currentIndex) {
                stepEl.classList.add("completed");
            } else if (index === currentIndex) {
                stepEl.classList.add("active");
            }
        });
    }

    // ── Toast notifications ─────────────────────────────────────────────
    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.style.cssText = `
            position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
            background: ${type === "error" ? "rgba(239,68,68,0.9)" : "rgba(15,15,28,0.95)"};
            color: white; padding: 12px 22px; border-radius: 10px;
            font-size: 0.875rem; font-weight: 500; z-index: 9999;
            border: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(12px);
            animation: fadeUp 0.3s ease;
            font-family: inherit;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }
});
