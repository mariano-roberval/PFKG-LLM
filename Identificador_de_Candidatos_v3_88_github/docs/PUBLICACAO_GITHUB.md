# Publicação no GitHub

1. Copie `config.example.json` para `config.json` e ajuste localmente.
2. Não envie `config.json`, `.env`, `output/`, `input/`, `dados/`, RDFs, HTMLs ou relatórios gerados.
3. Rode uma validação local:

```bash
python -m compileall .
streamlit run app_identificador_de_candidatos.py
```

4. Inicialize o repositório:

```bash
git init
git add .
git commit -m "Versão GitHub-safe do Identificador de Candidatos v3.88"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```
