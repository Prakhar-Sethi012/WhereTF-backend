<p align="center">
<a href="https://dscvit.com">
    <img width="400" src="https://user-images.githubusercontent.com/56252312/159312411-58410727-3933-4224-b43e-4e9b627838a3.png#gh-light-mode-only" alt="GDSC VIT"/>
</a>
</p>

<h2 align="center"> WhereTF </h2>
<h4 align="center"> WhereTF is an AI-powered file search tool that lets users find files using natural language and contextual memory instead of exact filenames. It understands file content and retrieves the most relevant results based on meaning, making file search faster and more intuitive. </h4>

---
<p align="center">
    <a href="https://dsc.community.dev/vellore-institute-of-technology/"><img src="https://img.shields.io/badge/Join%20Us-Developer%20Student%20Clubs-red" alt="Join Us"></a>
    <a href="https://discord.gg/498KVdSKWR"><img src="https://img.shields.io/discord/760928671698649098.svg" alt="Discord Chat"></a>
    <a href="INSERT_LINK_FOR_DOCS_HERE"><img src="https://img.shields.io/badge/Documentation-see%20docs-green?style=flat-square&logo=appveyor" alt="DOCS"></a>
    <a href="INSERT_UI_LINK_HERE"><img src="https://img.shields.io/badge/User%20Interface-Link%20to%20UI-orange?style=flat-square&logo=appveyor" alt="UI"></a>
</p>

## Features
- [x] Semantic searching across multiple file types
- [x] Multimodal image & text vectorization
- [x] Hybrid searching (semantic + keyword matching)
- [x] Query Expansion (via NLTK/WordNet)
- [x] Automated Indexing
- [x] Relationship Mapping

<br>

## Dependencies
- Docker
- Docker Compose
- PostgreSQL (with `pgvector` extension)

## Configuration (App Tiers)
WhereTF supports multiple performance tiers so you can run it on everything from a standard laptop to a dedicated server. You can change your tier by modifying the `APP_TIER` environment variable in your `docker-compose.yml`.

| Tier | RAM Usage | Text Embeddings | Vision Embeddings | EasyOCR |
|---|---|---|---|---|
| **`lite`** | ~700 MB | Yes (`all-MiniLM-L6-v2`) | No | Yes |
| **`balanced`** | ~1.2 GB | Yes (`nomic-embed-vision-v1.5`) | Yes (`nomic-embed-vision-v1.5`) | No |
| **`pro`** (Default)| ~2.0 GB | Yes (`jina-clip-v1`) | Yes (`jina-clip-v1`) | Yes |

* **Lite:** Best for older hardware. Uses a lightweight text model and relies entirely on OCR to read images.
* **Balanced:** Best middle-ground. Disables OCR to save PyTorch overhead, but enables state-of-the-art visual concept search using Nomic's highly efficient open-source vision model.
* **Pro:** Full feature set. Vectorizes text, visual concepts, AND extracts tiny text hidden inside diagrams and receipts using Jina CLIP and EasyOCR.

## Hardware Acceleration (CPU vs GPU)
By default, WhereTF builds a highly optimized **CPU-only** Docker image to save disk space (~150MB instead of 2.5GB of Nvidia drivers). 

If you have an Nvidia GPU and want to accelerate indexing and searching:
1. Open `docker-compose.yml`.
2. Under the `build` block for both the `backend` and `worker` services, set `USE_GPU: 1`.
3. Uncomment the `deploy` block in the compose file to pass GPU hardware capabilities to the container.
4. Run the build command below.

## Running

First, clone the repository and navigate into the project directory:
```bash
git clone [https://github.com/GDGVIT/WhereTF-backend](https://github.com/GDGVIT/WhereTF-backend)
cd WhereTF-backend

```

Start the application and database using Docker Compose. The `--build` flag ensures your chosen GPU/CPU architecture is compiled correctly:

```bash
docker-compose up --build -d

```

*(The backend will be available on port `8000`, and the database will be mapped to port `5433`)*

To stop the services:

```bash
docker-compose down

```

## Contributors

<table>
	<tr align="center">
		<td>
			<b>Maneet Gupta</b><br><br>
			<img src="https://github.com/RK-NerdyBirdy.png" width="150" height="150" style="border-radius:50%;" alt="Maneet Gupta"><br><br>
			<a href="https://github.com/RK-NerdyBirdy">GitHub</a> | 
			<a href="https://www.linkedin.com/in/maneet-gupta/">LinkedIn</a>
		</td>
		<td>
			<b>Aryan Rangarajan</b><br><br>
			<img src="https://github.com/Aryan-Ranga.png" width="150" height="150" style="border-radius:50%;" alt="Aryan Rangarajan"><br><br>
			<a href="https://github.com/Aryan-Ranga">GitHub</a> | 
			<a href="https://www.linkedin.com/in/aryan-rangarajan-791632371/">LinkedIn</a>
		</td>
		<td>
			<b>Prakhar Sethi</b><br><br>
			<img src="https://github.com/Prakhar-Sethi012.png" width="150" height="150" style="border-radius:50%;" alt="Prakhar Sethi"><br><br>
			<a href="https://github.com/Prakhar-Sethi012">GitHub</a> | 
			<a href="https://www.linkedin.com/in/prakhar-sethi-1a1818393/">LinkedIn</a>
		</td>
	</tr>
</table>

<br>
<p align="center">
	Made with ❤ by <a href="https://dscvit.com">GDSC-VIT</a>
</p>
