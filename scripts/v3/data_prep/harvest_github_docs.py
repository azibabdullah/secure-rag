import re, json, sys, concurrent.futures as cf, urllib.request, ssl, os
ctx=ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
REPOS="""psf/requests pallets/flask django/django fastapi/fastapi tiangolo/sqlmodel pandas-dev/pandas numpy/numpy scikit-learn/scikit-learn pytorch/pytorch huggingface/transformers
microsoft/vscode microsoft/TypeScript nodejs/node vercel/next.js facebook/react vuejs/core sveltejs/svelte angular/angular expressjs/express nestjs/nest
rust-lang/rust golang/go kubernetes/kubernetes docker/compose hashicorp/terraform ansible/ansible grafana/grafana prometheus/prometheus elastic/elasticsearch redis/redis
home-assistant/core esphome/esphome Klipper3d/klipper OctoPrint/OctoPrint pi-hole/pi-hole jellyfin/jellyfin nextcloud/server syncthing/syncthing obsproject/obs-studio
basecamp/handbook 18F/handbook 18F/guides github/docs mozilla/bedrock mdn/content opensource-design/resources todogroup/policies github/opensource.guide
rails/rails laravel/laravel symfony/symfony spring-projects/spring-boot apache/kafka apache/airflow dbt-labs/dbt-core streamlit/streamlit gradio-app/gradio ollama/ollama
ggerganov/llama.cpp langchain-ai/langchain run-llama/llama_index chroma-core/chroma qdrant/qdrant openai/openai-python anthropics/anthropic-sdk-python microsoft/PowerToys microsoft/terminal
git/git neovim/neovim tmux/tmux ohmyzsh/ohmyzsh junegunn/fzf BurntSushi/ripgrep sharkdp/bat jqlang/jq curl/curl openssl/openssl
nginx/nginx caddyserver/caddy traefik/traefik owncloud/core mattermost/mattermost RocketChat/Rocket.Chat discourse/discourse zulip/zulip signalapp/Signal-Desktop keepassxreboot/keepassxc
bitwarden/server vaultwarden/vaultwarden immich-app/immich photoprism/photoprism paperless-ngx/paperless-ngx firefly-iii/firefly-iii actualbudget/actual odoo/odoo frappe/erpnext invoiceninja/invoiceninja
moodle/moodle openedx/edx-platform kiwix/kiwix-tools zotero/zotero jgm/pandoc quarto-dev/quarto-cli jupyter/notebook jupyterlab/jupyterlab mkdocs/mkdocs sphinx-doc/sphinx
OWASP/CheatSheetSeries OWASP/wstg OWASP/ASVS owasp-modsecurity/ModSecurity-nginx SigmaHQ/sigma Yara-Rules/rules mitre/cti zaproxy/zaproxy wazuh/wazuh osquery/osquery
microsoft/Security-101 microsoft/ML-For-Beginners microsoft/Web-Dev-For-Beginners microsoft/AI-For-Beginners freeCodeCamp/freeCodeCamp EbookFoundation/free-programming-books kamranahmedse/developer-roadmap jwasham/coding-interview-university donnemartin/system-design-primer
arduino/Arduino adafruit/circuitpython micropython/micropython raspberrypi/documentation espressif/arduino-esp32 platformio/platformio-core qmk/qmk_firmware zmkfirmware/zmk betaflight/betaflight ArduPilot/ardupilot
""".split()
def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"securerag-harvest"}),timeout=20,context=ctx) as r:
            if r.status==200: return r.read().decode("utf-8","replace")
    except Exception: return None
def repo_docs(repo):
    out=[]
    for br in ("main","master"):
        base=f"https://raw.githubusercontent.com/{repo}/{br}/"
        for name in ("README.md","readme.md","README.rst","CONTRIBUTING.md","SECURITY.md",".github/CONTRIBUTING.md",".github/SECURITY.md","CODE_OF_CONDUCT.md","INSTALL.md","docs/README.md"):
            t=get(base+name)
            if t and len(t)>300: out.append((base+name,t))
        if out:
            # follow relative .md links from README
            rd=[t for u,t in out if u.lower().endswith(("readme.md",))]
            links=[]
            for t in rd:
                links+= [l for l in re.findall(r"\]\(([^)#\s]+\.md)\)",t) if not l.startswith("http")]
            for l in list(dict.fromkeys(links))[:12]:
                l=l.lstrip("./")
                t=get(base+l)
                if t and len(t)>300: out.append((base+l,t))
            break
    return repo,out
res={}
with cf.ThreadPoolExecutor(16) as ex:
    for repo,docs in ex.map(repo_docs,REPOS):
        res[repo]=[{"url":u,"text":t} for u,t in docs]
json.dump(res,open("gh/raw_docs.json","w"))
print("repos with docs",sum(1 for v in res.values() if v),"of",len(res),"docs",sum(len(v) for v in res.values()),"chars",sum(len(d["text"]) for v in res.values() for d in v))
