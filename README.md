# 🎬 Mosaico Thumbnail Pro

> Aplicativo desktop moderno para geração automatizada de mosaicos e folhas de contato (thumbnails) a partir de vídeos, com interface gráfica elegante em Dark Mode e suporte a processamento em lote.

---

## ✨ Funcionalidades

- 🎨 **Interface Moderna (Dark Mode)**: Construída em PySide6 (Qt) com visual Catppuccin / Dark moderno e responsivo.
- 📂 **Arrastar e Soltar (Drag & Drop)**: Adicione vídeos individuais ou pastas inteiras com facilidade.
- ⚡ **Processamento Rápido em Segundo Plano**: Extração paralela de quadros e renderização sem congelar a interface.
- 📐 **Grades Flexíveis de Mosaico**: Suporte a diversos formatos de grade (4x4, 5x4, 6x4, 6x5, 6x6, etc.).
- 🛠️ **Instalador Automático de FFmpeg**: Se o FFmpeg não for encontrado no sistema, o próprio aplicativo oferece para baixar e configurar automaticamente.
- ⏱️ **Métricas em Tempo Real**: Barra de progresso com alta legibilidade, estimativa de tempo restante (ETA) e estatísticas de processamento.
- 📦 **Compilação Portátil em 1 Clique**: Scripts prontos para empacotar o software em um executável `.exe` independente.

---

## 📋 Pré-requisitos

- **Python 3.10** ou superior instalado no Windows.
- **FFmpeg** (detectado automaticamente ou instalado pelo próprio programa).

---

## 🚀 Como Executar o Projeto

### 1. Clonar o repositório
```bash
git clone https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
cd APP_THUMBNAIL_v1
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
├── utils.py                         # Utilitários auxiliares do sistema
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
