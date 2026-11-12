import os
import io
import asyncio
import logging
from typing import Optional
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
import pandas as pd
import numpy as np
from fpdf import FPDF

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8217851677:AAHN34TMuC1P4e6SppuazFN8BIiLHa_RyIc")
OWNER_HANDLE = os.getenv("OWNER_HANDLE", "@Idrisov_prod")

def generate_pdf_report(df: pd.DataFrame, filename: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "DataPulse AI - Statistical Dossier", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 8, f"Source File: {filename} | Generated via DataPulse Engine", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    # General Info Table
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "1. Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Total Records (Rows): {len(df)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Total Features (Columns): {len(df.columns)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Missing Cells: {int(df.isna().sum().sum())}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Statistical Overview
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "2. Key Numeric Metrics (Mean, Median, Std, Outliers)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)

    col_widths = [45, 25, 25, 25, 25, 30]
    headers = ["Feature", "Mean", "Median", "Std Dev", "Min / Max", "Outliers (IQR)"]

    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()[:8]

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) == 0:
            continue
        mean_val = f"{series.mean():.2f}"
        med_val = f"{series.median():.2f}"
        std_val = f"{series.std():.2f}"
        min_max = f"{series.min():.1f} / {series.max():.1f}"

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        outliers = series[(series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)]
        out_str = f"{len(outliers)} ({len(outliers)/len(series)*100:.1f}%)"

        row_vals = [col[:22], mean_val, med_val, std_val, min_max, out_str]
        for i, val in enumerate(row_vals):
            pdf.cell(col_widths[i], 6, str(val), border=1, align="C")
        pdf.ln()

    pdf.ln(6)
    # Correlation Highlights
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "3. Top Pearson Correlation Pairs", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)

    num_df = df.select_dtypes(include=[np.number])
    if len(num_df.columns) >= 2:
        corr = num_df.corr().copy()
        for c in corr.columns:
            corr.loc[c, c] = 0.0
        corr_abs = corr.abs()
        unstacked = corr_abs.unstack().sort_values(ascending=False).drop_duplicates()
        top_pairs = unstacked.head(4)
        for (f1, f2), val in top_pairs.items():
            actual_val = corr.loc[f1, f2]
            pdf.cell(0, 6, f"* {f1} <-> {f2}: r = {actual_val:+.3f}", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 6, "Not enough numeric features for correlation analysis.", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 6, f"DataPulse AI Engine. Notifications dispatched to {OWNER_HANDLE}.", align="C")

    # Output to bytes
    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()

@router.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        "📊 *Добро пожаловать в DataPulse AI Bot!*\n\n"
        "Отправьте мне файл в формате *.CSV* или *.XLSX* (до 20 МБ), "
        "и я проведу полный статистический аудит данных:\n"
        "• Анализ пропусков и типов данных\n"
        "• Медианы, стандартные отклонения и интерквартильные размахи\n"
        "• Детекцию выбросов по методу Тьюки (IQR)\n"
        "• Матрицу корреляций Пирсона\n"
        "• Готовый многостраничный PDF-отчет для руководства!\n\n"
        "_Просто прикрепите документ к сообщению!_"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Открыть Web Dashboard", url="http://localhost:8003")],
        [InlineKeyboardButton(text="💬 Связь с создателем (@Idrisov_prod)", url="https://t.me/Idrisov_prod")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@router.message(F.document)
async def handle_document_upload(message: Message, bot: Bot):
    doc = message.document
    filename = doc.file_name or "dataset.csv"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in [".csv", ".xlsx", ".xls"]:
        await message.answer("⚠️ Пожалуйста, отправьте файл в формате *.CSV* или *.XLSX*.")
        return

    wait_msg = await message.answer(f"⏳ Анализирую `{filename}` и вычисляю статистические метрики...")

    try:
        # Download file buffer
        file_io = io.BytesIO()
        await bot.download(doc, destination=file_io)
        file_io.seek(0)

        if ext == ".csv":
            df = pd.read_csv(file_io)
        else:
            df = pd.read_excel(file_io)

        # Generate PDF report
        pdf_bytes = generate_pdf_report(df, filename)
        pdf_file = BufferedInputFile(pdf_bytes, filename=f"DataPulse_Report_{os.path.splitext(filename)[0]}.pdf")

        caption = (
            f"✅ *Аналитическое досье готово!*\n\n"
            f"📁 *Файл:* `{filename}`\n"
            f"📊 *Размер:* {len(df)} строк, {len(df.columns)} колонок.\n"
            f"📑 Сформирован PDF-отчет с ключевыми метриками и корреляциями.\n\n"
            f"Уведомление о запросе направлено: {OWNER_HANDLE}."
        )

        logger.info(f"DATAPULSE PDF GENERATED: {filename} ({len(df)} rows) for {message.from_user.id}")

        await wait_msg.delete()
        await message.answer_document(document=pdf_file, caption=caption, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error analyzing document: {e}")
        await wait_msg.edit_text(f"❌ Произошла ошибка при обработке таблицы: {str(e)}")

def create_datapulse_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    return bot, dp

async def main():
    bot, dp = create_datapulse_bot()
    logger.info("DataPulse AI Bot started polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
