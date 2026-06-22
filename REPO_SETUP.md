# PyFoldable — ayrı GitHub reposu kurulumu

Bu klasör, PyThrust `cursor/foldable-propeller-v1-2fe0` branch'inden üretilmiş **bağımsız repo** yapısıdır.

## GitHub'da yeni repo oluştur

1. https://github.com/new
2. Repository name: **PyFoldable**
3. **README / .gitignore / license eklemeyin** (boş repo)
4. Create repository

## Push

```bash
git remote set-url origin https://github.com/Poyqraz/PyFoldable.git
git push -u origin main
```

Veya:

```bash
./scripts/deploy_to_github.sh Poyqraz/PyFoldable main
```

## Alternatif: PyThrust branch'den clone

Repo henüz oluşturulmadıysa geçici olarak:

```bash
git clone -b pyfoldable-v1-2fe0 https://github.com/Poyqraz/PyThrust.git pyfoldable
```
