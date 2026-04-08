# ref2bibtex
Convert free-form academic references into LaTeX BibTeX entries via title-based retrieval with DBLP, Crossref, and Google Scholar fallback, plus a lightweight local web UI.

从普通 reference 文本中抽取论文标题，基于标题检索并返回 BibTeX。

检索顺序（`--source auto`）：
1. DBLP
2. Crossref
3. Google Scholar

## 安装依赖

```bash
python3 -m pip install -r plugins/ref-to-bibtex/scripts/requirements.txt
```

## 用法

```bash
python3 plugins/ref-to-bibtex/scripts/ref_to_bibtex.py \
  --reference '[12] Pan, Xudong, Mi Zhang, Yifan Yan, Shengyao Zhang, and Min Yang. "Matryoshka: Exploiting the over-parametrization of deep learning models for covert data transmission." IEEE Transactions on Pattern Analysis and Machine Intelligence 47, no. 2 (2024): 663-678.'
```

只输出 BibTeX（默认）：

```bash
python3 plugins/ref-to-bibtex/scripts/ref_to_bibtex.py -r '...'
```

输出结构化 JSON：

```bash
python3 plugins/ref-to-bibtex/scripts/ref_to_bibtex.py -r '...' --json
```

按来源强制检索：

```bash
python3 plugins/ref-to-bibtex/scripts/ref_to_bibtex.py -r '...' --source dblp
python3 plugins/ref-to-bibtex/scripts/ref_to_bibtex.py -r '...' --source crossref
python3 plugins/ref-to-bibtex/scripts/ref_to_bibtex.py -r '...' --source scholar
```

## 前端页面（本地）

启动本地服务：

```bash
python /Users/marriette/Downloads/ref-to-latex/plugins/ref-to-bibtex/scripts/web_app.py --port 8787
```

打开浏览器访问：

```text
http://127.0.0.1:8787
```

页面能力：
- 输入 reference 文本，一键生成 BibTeX
- 选择来源（auto / DBLP / Crossref / Google Scholar，auto 会按 DBLP -> Crossref -> Scholar 顺序回退）
- 显示匹配标题与来源
- 一键复制 BibTeX

## 说明

- 标题默认从引号中抽取（支持 `"..."` 和 `“...”`）。
- 如果 Google Scholar 出现反爬验证，脚本会返回失败并保留 DBLP 结果优先。
- 如果 reference 解析不到标题，可以直接传 `--title`。
