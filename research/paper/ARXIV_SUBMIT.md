# Подання препринта на arXiv

## Перед поданням

1. У тексті не лишилося позначок `\TBD{...}` (їх перевіряє `build_arxiv.py`).
2. Рисунки, таблицю синтетичних помилок і список літератури оновлено:

   ```
   python figures.py
   python tables.py
   python bib2tex.py
   python build_arxiv.py
   ```

   Результат — `arxiv_upload.zip` (`main.tex` + `figs/*.pdf`).
3. Співавтор погодив остаточний текст.

## Подання (≈15 хв)

1. https://arxiv.org/submit → **Start new submission**. Ліцензія — CC BY 4.0.
2. **Files**: завантажте `arxiv_upload.zip`, arXiv розпакує його сам.
3. **Process**: arXiv скомпілює PDF. Перевірте: титульна сторінка з двома авторами, 3 таблиці результатів,
   3 рисунки (схема конвеєра, recall за типами помилок, важливість ознак), список літератури з номерами.
   Якщо компіляція впала — збережіть текст помилки з логу.
4. **Metadata**: поля з `arxiv_metadata.txt`; анотацію — з `_abstract.txt` одним абзацом.
5. **Preview** → **Submit**. Препринт з'явиться після найближчого оголошення arXiv
   (зазвичай наступного робочого дня о 20:00 UTC).

## Після появи на arXiv

- Додати номер arXiv у `README.md` (розділ «Ліцензія та цитування») і в `research/README.md`.
- Подання в Decision Support Systems: перенесення в шаблон `elsarticle`, highlights, супровідний лист.
