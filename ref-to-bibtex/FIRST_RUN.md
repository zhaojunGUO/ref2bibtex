# Ref-to-BibTeX 首次使用指南

这份文档给第一次使用的人，按顺序执行即可。

## 1. 进入项目目录

```bash
cd ref-to-latex
```

## 2. 创建 Conda 环境

```bash
conda create -n ref-to-bibtex python=3.11 -y
conda activate ref-to-bibtex
```

## 3. 安装依赖

```bash
python -m pip install --upgrade pip
python -m pip install -r ref-to-latex/plugins/ref-to-bibtex/scripts/requirements.txt
```

如果你看到 `ModuleNotFoundError: No module named 'requests'`，说明依赖没装到当前环境，重新执行第 2、3 步。

## 4. 验证安装

```bash
which python
python -m pip show requests
python ref-to-latex/plugins/ref-to-bibtex/scripts/ref_to_bibtex.py --help
```

## 5. 方式 A：命令行运行

```bash
python ref-to-latex/plugins/ref-to-bibtex/scripts/ref_to_bibtex.py \
  --reference '[12] Pan, Xudong, Mi Zhang, Yifan Yan, Shengyao Zhang, and Min Yang. "Matryoshka: Exploiting the over-parametrization of deep learning models for covert data transmission." IEEE Transactions on Pattern Analysis and Machine Intelligence 47, no. 2 (2024): 663-678.'
```

可选参数：
- `--source auto|dblp|crossref|scholar`：检索来源（默认 `auto`，顺序为 DBLP -> Crossref -> Scholar）。
- `--json`：输出 JSON（包含匹配标题和来源）。
- `--title "..."`：手动指定标题（当 reference 无法正确抽取标题时）。

## 6. 方式 B：前端页面运行

启动本地服务：

```bash
python ref-to-latex/plugins/ref-to-bibtex/scripts/web_app.py --port 8787
```

浏览器打开：

```text
http://127.0.0.1:8787
```

使用步骤：
1. 粘贴 reference 文本。
2. 选择来源（建议先用 `auto`）。
3. 点击“生成 BibTeX”。
4. 点击“复制 BibTeX”保存结果。

## 7. 常见问题

- `ModuleNotFoundError`：当前 shell 没激活对的 conda 环境，执行 `conda activate ref-to-bibtex` 后重装依赖。
- Google Scholar 失败：可能触发反爬限制，先用 `--source auto` 或 `--source crossref`。
- 抽取标题失败：改用 `--title` 显式传论文标题。

## 8. 相关文件

- CLI 脚本：`ref-to-latex/plugins/ref-to-bibtex/scripts/ref_to_bibtex.py`
- Web 服务：`ref-to-latex/plugins/ref-to-bibtex/scripts/web_app.py`
- 前端页面：`ref-to-latex/plugins/ref-to-bibtex/web/index.html`
- 依赖文件：`ref-to-latex/plugins/ref-to-bibtex/scripts/requirements.txt`
