# Deploying the Cirqle backend to AWS (EC2, Amazon Linux 2023)

Follow this once your AWS account is fully activated. Total hands-on time: ~10 minutes.

The heavy lifting is automated by [`deploy/setup.sh`](deploy/setup.sh) — you launch a
server, connect to it, and paste **one command**.

---

## Stage 1 — Launch the server (AWS console)

1. Sign in to AWS → search **EC2** → open it.
2. **Top-right, set your Region** to **Europe (London) `eu-west-2`** (UK users). The
   server lives in the selected region, so choose it *before* launching.
3. Click **Launch instance**.
4. **Name:** `cirqle-backend`
5. **OS Image (AMI):** **Amazon Linux 2023**, 64-bit (x86). ("Free tier eligible.")
6. **Instance type:** the one labelled **Free tier eligible** (`t2.micro` or `t3.micro`).
7. **Key pair:** Create new key pair → `cirqle-key`, RSA, `.pem` → save the download
   to `~/.ssh/` (backup; we connect via the browser).
8. **Network settings → Edit → add these firewall rules:**

   | Type       | Port | Source          |
   |------------|------|-----------------|
   | SSH        | 22   | Anywhere 0.0.0.0/0 |
   | HTTP       | 80   | Anywhere        |
   | HTTPS      | 443  | Anywhere        |
   | Custom TCP | 8000 | Anywhere        |

9. **Storage:** default 8 GB is fine.
10. **Launch instance** → **View all instances** → wait for **Running** + **2/2 checks passed**.
11. Copy the **Public IPv4 address**.

## Stage 2 — Connect to the server (from your Mac's Terminal)

SSH is locked to your IP, so connect with the key you downloaded. (The browser
"Connect" button won't work with a My-IP rule — it comes from AWS's IP, not yours.)

```bash
mv ~/Downloads/cirqle-key.pem ~/.ssh/ 2>/dev/null   # if it's still in Downloads
chmod 400 ~/.ssh/cirqle-key.pem                      # lock down the key file
ssh -i ~/.ssh/cirqle-key.pem ec2-user@YOUR_SERVER_IP
```

Type `yes` at the fingerprint prompt the first time. You're now on the server.

## Stage 3 — Bring the API online (one command)

Paste this into that browser terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/gkg-gkg/Cirrqle-Fable/main/backend/deploy/setup.sh | bash
```

It installs Python, pulls the code, creates a virtualenv, generates a secret key,
and starts the API as a background service. When it finishes you'll see the service
marked **active (running)**.

## Stage 4 — Test it live

From your **laptop** (replace with your instance's public IP):

```bash
curl http://YOUR_SERVER_IP:8000/
# {"status":"ok","service":"cirqle-api"}
```

## Stage 5 — Point the website at the live API

Edit [`assets/api.js`](../assets/api.js) so the production URL is your server, then
commit + redeploy the frontend. Login/signup on the live site now use AWS.

> ⚠️ **Mixed content:** if your website is served over **https://**, the browser will
> block calls to a plain **http://** API. So for the *public* site to work, the API
> needs HTTPS — see Stage 6. (Local testing over http:// works right away.)

## Stage 6 — HTTPS + domain (production)

1. Point a domain/subdomain (e.g. `api.cirqle.example`) at the server's public IP
   (an **A record**).
2. Install [Caddy](https://caddyserver.com), which auto-provisions a free TLS
   certificate. Reverse-proxy `443 → 127.0.0.1:8000`. (Commands provided when you
   reach this step.)
3. Update `assets/api.js` to the `https://api.cirqle.example` URL.

---

## Managing the service (handy commands, run on the server)

```bash
sudo systemctl status cirqle-api     # is it running?
sudo systemctl restart cirqle-api    # restart it
journalctl -u cirqle-api -n 50 --no-pager   # last 50 log lines
```

## Deploying a code update later

Re-run the same one-liner from Stage 3 — it pulls the latest code and restarts the
service, keeping your `.env` and database intact.
