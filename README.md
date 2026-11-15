# 🎬 Mosaico Thumbnail Pro

> Aplicativo desktop moderno para geração automatizada de mosaicos e folhas de contato (thumbnails) a partir de vídeos, com interface gráfica elegante em Dark Mode e suporte a processamento em lote.

---

## 📥 Download da Versão Pronta para Uso (.EXE)

Se você deseja apenas **usar o aplicativo** no Windows sem precisar instalar Python ou mexer em código:

1. Acesse a aba de **[Releases](https://github.com/joaopaulo-rds/mosaico-thumbnail-pro/releases)** do repositório.
2. Baixe o arquivo **`MosaicoThumbnailPro_Portatil.exe`**.
3. Dê dois cliques para executar!

---

## ⚙️ Como o programa lida com o FFmpeg (Instalação 100% Automática)

Para gerar os mosaicos de fotos em alta performance, o aplicativo utiliza o poder do **FFmpeg** e do **FFprobe**:

- **Por que eles são necessários?**
  - O `MosaicoThumbnailPro_Portatil.exe` cuida de toda a interface gráfica, cálculo de tempo e gerenciamento das tarefas.
  - O `ffprobe.exe` é o inspetor que lê a duração, resolução e formato do vídeo em milissegundos.
  - O `ffmpeg.exe` é o motor de alta velocidade que extrai com precisão cirúrgica os quadros do vídeo para montar o mosaico.

- **Por que eles não vêm "embutidos" dentro do executável?**
  - Para manter o seu aplicativo super leve (~50 MB) e rápido para abrir, em vez de gerar um arquivo pesado de mais de 230 MB.

- **Preciso instalar o FFmpeg manualmente?**
  - **Não!** Na primeira vez que você abrir o executável, se o FFmpeg não for detectado no computador, o aplicativo exibirá um aviso amigável na tela perguntando se você deseja baixá-lo automaticamente.
  - Ao clicar em **"Sim"**, o próprio aplicativo baixa os arquivos oficiais e os salva na mesma pasta, pronto para funcionar para sempre (inclusive offline).

---

## ✨ Funcionalidades

- 📑 **Sistema com 3 Modos / Abas Independentes**:
  - 🎬 **Converter para MP4**: Conversão otimizada (H.264/AAC) com a capa mosaico embutida no arquivo.
  - 🎞️ **Converter para MKV**: Conversão Matroska com anexo oficial de capa (`cover.jpg` mime `image/jpeg`).
  - 🖼️ **Apenas Imagem Mosaico**: Geração ultra-rápida de folhas de contato (JPG ou PNG com qualidade ajustável) sem alterar os arquivos de vídeo.
- 🎨 **Interface Moderna (Dark Mode)**: Construída em PySide6 (Qt) com visual Dark moderno, limpo e responsivo.
- 📂 **Arrastar e Soltar (Drag & Drop)**: Adicione vídeos individuais ou pastas inteiras com facilidade.
- ⚡ **Processamento Rápido em Segundo Plano**: Extração paralela de quadros e renderização sem congelar a interface.
- ⏭️ **Controle de Execução Flexível**: Opções para Pausar, Retomar, Cancelar ou **Pular o vídeo atual** sob demanda.
- 🛡️ **Cão de Guarda Anti-Congelamento**: Monitoramento contínuo dos processos do FFmpeg para evitar travamentos em arquivos corrompidos.
- 📐 **Grades Flexíveis de Mosaico**: Suporte a diversos formatos de grade (4x4, 5x4, 6x4, 6x5, 6x6, etc.).
- 🛠️ **Instalador Automático Integrado**: O próprio aplicativo gerencia o download e configuração do FFmpeg.
- ⏱️ **Métricas em Tempo Real**: Barra de progresso com alta legibilidade, estimativa de tempo restante (ETA) e estatísticas de processamento.
- 📦 **Compilação Portátil em 1 Clique**: Scripts prontos para empacotar o software em um executável autônomo.

---

## 📋 Pré-requisitos (Apenas para Desenvolvedores)

Se você for rodar ou modificar o código-fonte em Python:
- **Python 3.10** ou superior instalado no Windows.
- Dependências listadas no `requirements.txt`.

---

## 🚀 Como Executar o Código-Fonte

### 1. Clonar o repositório
```bash
git clone https://github.com/joaopaulo-rds/mosaico-thumbnail-pro.git
cd mosaico-thumbnail-pro
```

### 2. (Opcional) Criar e ativar um ambiente virtual
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Instalar as dependências
```powershell
pip install -r requirements.txt
```

### 4. Executar o aplicativo
```powershell
python main.py
```

---

## 📦 Gerando o Executável (.exe) Portátil

Você pode compilar o projeto em um executável autônomo com ícone oficial:

- **Opção 1 (1 Clique)**: Execute o arquivo `GERAR_EXECUTAVEL_COM_1_CLIQUE.bat`.
- **Opção 2 (Terminal)**:
  ```powershell
  python -m PyInstaller --noconfirm --onefile --windowed --name "MosaicoThumbnailPro_Portatil" --icon="icon.ico" --add-data "icon.png;." --clean main.py
  ```

O executável final será salvo na pasta `dist/MosaicoThumbnailPro_Portatil.exe`.

> 💡 *Para um passo a passo mais detalhado, consulte o arquivo [`GUIA_PASSO_A_PASSO.md`](GUIA_PASSO_A_PASSO.md).*

---

## 📁 Estrutura do Projeto

```text
├── main.py                          # Ponto de entrada da aplicação
├── gui.py                           # Interface gráfica (PySide6)
├── processor.py                     # Motor de processamento de vídeo e FFmpeg
├── utils.py                         # Utilitários auxiliares do sistema e instalador do FFmpeg
├── requirements.txt                 # Dependências do projeto
├── icon.ico / icon.png              # Identidade visual e ícones
├── GERAR_EXECUTAVEL_COM_1_CLIQUE.bat # Script de automação de build (PyInstaller)
├── ABRIR_PASTA_DO_EXECUTAVEL.bat     # Atalho para pasta dist
├── GUIA_PASSO_A_PASSO.md            # Guia passo a passo complementar
└── README.md                        # Documentação principal do repositório
```

---

## 📄 Licença

Este projeto é disponibilizado sob a licença [MIT](LICENSE).
