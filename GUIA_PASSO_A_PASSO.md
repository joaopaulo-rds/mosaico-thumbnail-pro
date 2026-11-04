# 📘 Guia de Instalação e Uso: Mosaico Thumbnail Pro

Este é o guia passo a passo completo para instalar as dependências, executar e gerar o aplicativo `.exe` portátil no Windows.

---

## 📋 Pré-requisitos
Para rodar este aplicativo, você precisará de:
1. **Python 3.10 ou superior** instalado no Windows.
2. **FFmpeg** (o aplicativo baixa e instala o FFmpeg automaticamente se não encontrar no seu PC!).

---

## 🛠️ Passo 1: Instalação do Python no Windows

1. Acesse o site oficial do Python: [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Baixe o instalador da versão mais recente (ex: Python 3.11 ou 3.12).
3. **MUITO IMPORTANTE:** Ao abrir o instalador, **marque a opção** `Add python.exe to PATH` na primeira tela.
4. Clique em **Install Now** e aguarde a conclusão.
5. Para verificar a instalação, abra o Prompt de Comando (CMD) ou PowerShell e digite:
   ```bash
   py --version
   ```

---

## 🎬 Passo 2: Instalação do FFmpeg no Windows (Automática)

O **Mosaico Thumbnail Pro** possui **instalador automático de FFmpeg integrado**. 

Ao abrir o aplicativo pela primeira vez, se ele não detectar o FFmpeg no seu computador, exibirá um aviso oferecendo para baixar e instalar o FFmpeg automaticamente. Basta clicar em **"Sim"**!

*(Opção alternativa)*: Você também pode copiar os arquivos `ffmpeg.exe` e `ffprobe.exe` para dentro da mesma pasta do programa.

---

## 📦 Passo 3: Instalação das Dependências do Projeto

1. Abra o Prompt de Comando (CMD) ou PowerShell.
2. Navegue até a pasta do projeto:
   ```powershell
   cd f:\00-ARQUIVOS-ANTIGOS\18-APP-CRIADOS\APP_THUMBNAIL_v1
   ```
3. Instale as bibliotecas requeridas executando:
   ```powershell
   py -m pip install -r requirements.txt
   ```

---

## 🚀 Passo 4: Executando o Aplicativo em Modo Desenvolvedor

Com as dependências instaladas, rode o comando:
```powershell
py main.py
```
A interface gráfica em Dark Mode do **Mosaico Thumbnail Pro** será iniciada.

---

## 📦 Passo 5: Gerando o Executável (.exe) Portátil para Windows com 1 Clique

Você tem duas opções simples para compilar o programa em um arquivo `.exe`:

### Opção A (Recomendada - 1 Clique):
Basta dar dois cliques no arquivo:
👉 **`GERAR_EXECUTAVEL_COM_1_CLIQUE.bat`**

### Opção B (Via Terminal):
```powershell
py -m PyInstaller --noconfirm --onefile --windowed --name "MosaicoThumbnailPro_Portatil" --icon="icon.ico" --add-data "icon.png;." --clean main.py
```

O arquivo executável final com o ícone oficial será gerado em:
👉 **`dist/MosaicoThumbnailPro_Portatil.exe`**

---

## 📁 Estrutura dos Arquivos do Projeto

- **`main.py`**: Ponto de entrada do aplicativo com configuração de nome e ícone.
- **`gui.py`**: Interface gráfica moderna (PySide6 Dark Mode) com arrastar e soltar, estimativa de tempo (ETA), barra de progresso em tempo real com texto em preto alto contraste e seleção de grades (4x4, 5x4, 6x4, 6x5, 6x6, etc.).
- **`processor.py`**: Motor de processamento em segundo plano (QThread), leitura de progresso do FFmpeg (`-progress pipe:1`), extração paralela de quadros, conversão para `.MP4` e restauração de datas.
- **`utils.py`**: Funções auxiliares (datas, notificação do Windows Shell `SHChangeNotify`, detector de executáveis).
- **`icon.ico` / `icon.png`**: Ícones oficiais do aplicativo.
- **`requirements.txt`**: Lista de dependências Python.
- **`GERAR_EXECUTAVEL_COM_1_CLIQUE.bat`**: Atalho de compilação em 1 clique.
- **`ABRIR_PASTA_DO_EXECUTAVEL.bat`**: Atalho para abrir a pasta `dist` onde o aplicativo está salvo.
- **`GUIA_PASSO_A_PASSO.md`**: Este guia de instruções.
