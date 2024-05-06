---
page_type: sample
languages:
- python
products:
- azure
- azure-ai-search
- azure-document-intelligence
name: Document Intelligence Image Extract Custom Skill
urlFragment: azure-document-intelligence-image-extract-skill
description: This custom skill uses Azure AI Document Intelligence's pre-trained layout models to extract images and fields from forms.
---
# Image Extract Custom Skill for Azure AI Search
このカスタムスキルは、Azure AI Document Intelligence のレイアウトモデルを使用して PDF などのドキュメントから画像を抽出します。抽出した画像データは Azure Data Lake Storage Gen2 に保存します。

# Deployment

本スキルは、[Azure AI Document Intelligence](https://azure.microsoft.com/products/ai-services/ai-document-intelligence) リソースおよび、[Azure Data Lake Storage Gen2](https://learn.microsoft.com/azure/storage/blobs/data-lake-storage-introduction)（ストレージアカウント）リソースが必要です。また、`DOCUMENT_INTELLIGENCE_ENDPOINT` と `DOCUMENT_INTELLIGENCE_KEY` および、`AZURE_STORAGE_CONNECTION_STRING`、`AZURE_STORAGE_CONTAINER_NAME` が必要です。Azure Functions にデプロイする際は、**「アプリケーション設定」項目に設定する必要**があります。

## スキルのデプロイ方法
1. Azure portal で、Azure AI Document Intelligence [リソースを作成](https://learn.microsoft.com/azure/ai-services/document-intelligence/create-document-intelligence-resource?view=doc-intel-4.0.0)します。
1. Azure AI Document Intelligence の API キーとエンドポイントをコピーします。
1. ストレージアカウント [リソースを作成](https://learn.microsoft.com/azure/storage/blobs/create-data-lake-storage-account)します。
1. ストレージブラウザーや [Azure Storage Explorer](https://azure.microsoft.com/products/storage/storage-explorer) を使用して画像ファイル出力先のコンテナを作成します。
1. ストレージアカウントの接続文字列とコンテナ名をコピーします。
1. このレポジトリを clone します。
1. Visual Studio Code でレポジトリのフォルダを開き、Azure Functions にリモートデプロイします。
1. Functions にデプロイが完了したら, Azure Portal の Azure Functions の設定→環境変数から、`DOCUMENT_INTELLIGENCE_ENDPOINT` と `DOCUMENT_INTELLIGENCE_KEY`、および`AZURE_STORAGE_CONNECTION_STRING`、`AZURE_STORAGE_CONTAINER_NAME` 環境変数を作成してそれぞれ値を貼り付けます。



## Requirements

Azure Functions へデプロイする場合、以下が必要となります。

- [Visual Studio Code](https://azure.microsoft.com/products/visual-studio-code/)
- [Azure Functions for Visual Studio Code](https://learn.microsoft.com/azure/azure-functions/functions-develop-vs-code?tabs=node-v3%2Cpython-v2%2Cisolated-process&pivots=programming-language-python)

## Settings

この Funcsions は、有効な Azure AI Document Intelligence API キーが設定された `DOCUMENT_INTELLIGENCE_KEY` の設定と、Azure AI Document Intelligence エンドポイント `DOCUMENT_INTELLIGENCE_ENDPOINT` を必要とします。また、ストレージアカウント リソースも同様に必要です。
ローカルで実行する場合は、プロジェクトのローカル環境変数 `local.settings.json` で設定できます。これにより、API キーが誤ってコードに埋め込まれることがなくなります。
Azure Functions で実行する場合、これは「アプリケーションの設定」で設定できます。


## Sample Input:

カスタムスキルは画像の `data` 項目などを Azure AI Search から受け取ります。`data` 項目には Azure AI Document Intelligence に渡すためのファイル URL と SAS トークンが含まれます。分析に使用するモデルも指定できるようになっていますが、基本的には `prebuilt-layout` を使用します。

```json
{
    "values": [
        {
            "recordId": "record1",
            "data": { 
                "model": "prebuilt-layout",
                "formUrl": "https://xxx.blob.core.windows.net/xxx/layout-pageobject.pdf",
                "formSasToken":  "?st=sasTokenThatWillBeGeneratedByCognitiveSearch"
            }
        }
    ]
}
```

## Sample Output:

```json
{
    "values": [
        {
            "recordId": "record1",
            "paragraphs": [
                {
                    "id": "paragraphs/0",
                    "content": "<!-- PageHeader=\"This is the header of the document.\" -->",
                    "role": "pageHeader"
                }
            ],
            "sections": [
                [
                    "/paragraphs/1",
                    "/sections/1",
                    "/sections/2",
                    "/sections/5"
                ],
            ],
            "content": "<!-- PageHeader=\"This is the header of the document.\" -->\n\nThis is title\n===\n\n\n# 1\\.",
            "figures": [
                {
                    "pageNumber": 1,
                    "caption": "Figure 1: Here is a figure with text",
                    "image": "figure_1_figure_1_here_is_a_figure_with_text.png",
                    "polygon": [
                        1.0301,
                        7.1098,
                        4.1763,
                        7.1074,
                        4.1781,
                        9.0873,
                        1.0324,
                        9.0891
                    ],
                    "elements": [
                        "/paragraphs/16",
                        "/paragraphs/17",
                        "/paragraphs/18",
                    ]
                }
            ]
        }
    ]
}
```

## スキルセット統合の例

このスキルを Azure AI Search パイプラインで使用するには、スキル定義をスキルセットに追加する必要があります。この例のスキル定義の例を次に示します（特定のシナリオとスキルセット環境を反映するように入力と出力を更新する必要があります）。

```json
{
    "@odata.type": "#Microsoft.Skills.Custom.WebApiSkill",
    "name": "ImageExtractSkill",
    "description": "Extracts images and fields from a form using a pre-trained layout model",
    "uri": "[AzureFunctionEndpointUrl]/api/analyze?code=[AzureFunctionDefaultHostKey]",
    "context": "/document",
    "inputs": [
        {
            "name": "formUrl",
            "source": "/document/metadata_storage_path_raw"
        },
        {
            "name": "formSasToken",
            "source": "/document/metadata_storage_sas_token"
        },
        {
            "name": "model",
            "source": "= 'prebuilt-layout'"
        }
    ],
    "outputs": [
        {
            "name": "paragraphs",
            "targetName": "paragraphs"
        },
        {
            "name": "sections",
            "targetName": "sections"
        },
        {
            "name": "content",
            "targetName": "markdown"
        },
        {
            "name": "figures",
            "targetName": "figures"
        }
    ]
}
```

## インデクサー設定の例
インデクサーに出力フィールドのマッピングを設定します。これを行わないと、エンリッチ処理されたツリーから取得したデータを検索フィールドへマッピングすることができません。

```json
{
  "outputFieldMappings": [
    {
      "sourceFieldName": "/document/paragraphs",
      "targetFieldName": "paragraphs"
    },
    {
      "sourceFieldName": "/document/sections",
      "targetFieldName": "sections"
    },
    {
      "sourceFieldName": "/document/markdown",
      "targetFieldName": "markdown"
    },
    {
      "sourceFieldName": "/document/figures",
      "targetFieldName": "figures"
    }
  ]
}
```