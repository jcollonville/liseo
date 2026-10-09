#!/usr/bin/env python3
"""Strip DRM-removal features from a libgourou source tree.

Removes adept_remove, removeDRM (and its helpers), private-key export, and
anonymous activation. Intended to be applied to upstream v0.8.10
(906b8a37334ac5d37dcae24c7508a427c19dbb66) before compilation.

The Docker image builds from the pinned upstream commit and this patch.
This script is the generator; patches/libgourou-no-drm-removal.patch is the
artifact applied at build time.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _delete_function(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"function not found: {signature}")
    # Include a preceding block comment when it sits immediately above.
    comment = text.rfind("/**", 0, start)
    if comment != -1:
        between = text[comment:start]
        if between.count("/**") == 1 and "*/" in between and between.strip().endswith("*/") is False:
            # Only swallow the comment when nothing but whitespace follows it.
            tail = between.split("*/", 1)[1]
            if tail.strip() == "":
                start = comment
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"no brace for {signature}")
    depth = 0
    i = brace
    while i < len(text):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                if end < len(text) and text[end] == "\n":
                    end += 1
                return text[:start] + text[end:]
        i += 1
    raise SystemExit(f"unbalanced braces for {signature}")


def _must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"pattern not found: {label}")
    return text.replace(old, new, 1)


def restrict(root: Path) -> None:
    header = root / "include" / "libgourou.h"
    header_text = header.read_text()
    header_text = _must_replace(
        header_text,
        """
        /**
         * @brief Export clear private license key into path
         */
        void exportPrivateLicenseKey(std::string path);

""",
        "\n",
        "exportPrivateLicenseKey declaration",
    )
    header_text = _must_replace(
        header_text,
        """
        /**
         * @brief Remove ADEPT DRM
         * Warning: for PDF format, filenameIn must be different than filenameOut
         *
         * @param filenameIn         Input file (with ADEPT DRM)
         * @param filenameOut        Output file (without ADEPT DRM)
         * @param type               Type of file (ePub or PDF)
         * @param encryptionKey      Optional encryption key, do not try to decrypt the one inside input file
         * @param encryptionKeySize  Size of encryption key (if provided)
         */
        void removeDRM(const std::string& filenameIn, const std::string& filenameOut, ITEM_TYPE type, const unsigned char* encryptionKey=0, unsigned encryptionKeySize=0);

""",
        "\n",
        "removeDRM declaration",
    )
    header_text = _must_replace(
        header_text,
        """        std::string encryptedKeyFirstPass(pugi::xml_document& rightsDoc, const std::string& encryptedKey, const std::string& keyType);
        void decryptADEPTKey(pugi::xml_document& rightsDoc, unsigned char* decryptedKey, const unsigned char* encryptionKey=0, unsigned encryptionKeySize=0);
        void removeEPubDRM(const std::string& filenameIn, const std::string& filenameOut, const unsigned char* encryptionKey, unsigned encryptionKeySize);
        void generatePDFObjectKey(int version,
                                  const unsigned char* masterKey, unsigned int masterKeyLength,
                                  int objectId, int objectGenerationNumber,
                                  unsigned char* keyOut);
        void removePDFDRM(const std::string& filenameIn, const std::string& filenameOut, const unsigned char* encryptionKey, unsigned encryptionKeySize);
""",
        "",
        "private DRM-removal helpers",
    )
    header.write_text(header_text)

    source = root / "src" / "libgourou.cpp"
    source_text = source.read_text()
    source_text = _must_replace(
        source_text,
        """        if (adobeID == "anonymous")
            signIn.append_attribute("method") = "anonymous";
        else if (loginMethod.size())
""",
        """        if (adobeID == "anonymous")
        {
            EXCEPTION(SIGN_INVALID_CREDENTIALS, "Anonymous activation is disabled");
        }
        else if (loginMethod.size())
""",
        "anonymous sign-in",
    )
    for signature in (
        "void DRMProcessor::exportPrivateLicenseKey",
        "std::string DRMProcessor::encryptedKeyFirstPass",
        "void DRMProcessor::decryptADEPTKey",
        "void DRMProcessor::removeEPubDRM",
        "void DRMProcessor::generatePDFObjectKey",
        "void DRMProcessor::removePDFDRM",
        "void DRMProcessor::removeDRM",
    ):
        source_text = _delete_function(source_text, signature)
    source.write_text(source_text)

    user = root / "src" / "user.cpp"
    user_text = user.read_text()
    user_text = _must_replace(
        user_text,
        """            if (loginMethod == "anonymous")
                username = "anonymous";
            else
                username    = gourou::extractTextElem(activationDoc, "//adept:username", throwOnNull);
""",
        """            if (loginMethod == "anonymous")
                EXCEPTION(USER_INVALID_ACTIVATION_FILE, "Anonymous activation is disabled");
            username = gourou::extractTextElem(activationDoc, "//adept:username", throwOnNull);
""",
        "anonymous activation load",
    )
    user.write_text(user_text)

    makefile = root / "utils" / "Makefile"
    make_text = makefile.read_text()
    make_text = _must_replace(
        make_text,
        "TARGET_BINARIES=acsmdownloader adept_activate adept_remove adept_loan_mgt\n",
        "TARGET_BINARIES=acsmdownloader adept_activate adept_loan_mgt\n",
        "utils binaries",
    )
    make_text = _must_replace(
        make_text,
        "MAN_PAGES=acsmdownloader adept_activate adept_remove adept_loan_mgt\n",
        "MAN_PAGES=acsmdownloader adept_activate adept_loan_mgt\n",
        "man pages",
    )
    makefile.write_text(make_text)

    activate = root / "utils" / "adept_activate.cpp"
    activate_text = activate.read_text()
    activate_text = _must_replace(
        activate_text,
        '    std::cout << "  " << "-a|--anonymous"  << "\\t"   << "Anonymous account, no need for username/password (Use it only with a DRM removal software)" << std::endl;\n',
        "",
        "anonymous help",
    )
    activate_text = _must_replace(
        activate_text,
        "    bool anonymous = false;\n\n",
        "\n",
        "anonymous flag",
    )
    activate_text = _must_replace(
        activate_text,
        '            {"anonymous",     no_argument      , 0,  \'a\' },\n',
        "",
        "anonymous long option",
    )
    activate_text = _must_replace(
        activate_text,
        '        c = getopt_long(argc, argv, "au:p:O:H:rvVh",\n',
        '        c = getopt_long(argc, argv, "u:p:O:H:rvVh",\n',
        "activate getopt",
    )
    activate_text = _must_replace(
        activate_text,
        """        case 'a':
            anonymous = true;
            break;
        case 'u':
""",
        """        case 'u':
""",
        "anonymous case",
    )
    activate_text = _must_replace(
        activate_text,
        """    if ((!username && !anonymous) ||
        (username && anonymous))
    {
        usage(argv[0]);
        return -1;
    }

    if (anonymous)
    {
        username = "anonymous";
        password = "";
    }

""",
        """    if (!username)
    {
        usage(argv[0]);
        return -1;
    }

""",
        "anonymous username logic",
    )
    activate.write_text(activate_text)

    downloader = root / "utils" / "acsmdownloader.cpp"
    down_text = downloader.read_text()
    down_text = _must_replace(
        down_text,
        "static       bool  exportPrivateKey = false;\n",
        "",
        "export flag",
    )
    down_text = _must_replace(
        down_text,
        """            gourou::DRMProcessor processor(&client, deviceFile, activationFile, devicekeyFile);
            gourou::User* user = processor.getUser();
    
            if (exportPrivateKey)
            {
                std::string filename;
                if (outputFile)
                    filename = outputFile;
                else
                {
                    filename = std::string("Adobe_PrivateLicenseKey--") + user->getUsername() + ".der";

                    if (outputDir)
                        filename = std::string(outputDir) + "/" + filename;
                }

                createPath(filename.c_str());
                
                processor.exportPrivateLicenseKey(filename);

                std::cout << "Private license key exported to " << filename << std::endl;
            }
            else
            {
                gourou::FulfillmentItem* item = processor.fulfill(acsmFile, notify);
""",
        """            gourou::DRMProcessor processor(&client, deviceFile, activationFile, devicekeyFile);
            gourou::FulfillmentItem* item = processor.fulfill(acsmFile, notify);
""",
        "export branch",
    )
    # The former else-block's closing brace must go, leaving fulfill/download in place.
    down_text = _must_replace(
        down_text,
        """                serializeLoanToken(item);
            }
        } catch(std::exception& e)
""",
        """                serializeLoanToken(item);
        } catch(std::exception& e)
""",
        "export else close",
    )
    down_text = _must_replace(
        down_text,
        '    std::cout << "  " << "-e|--export-private-key"<< "\\t" << "Export private key in DER format" << std::endl;\n',
        "",
        "export help",
    )
    down_text = _must_replace(
        down_text,
        '            {"export-private-key",no_argument,      0,  \'e\' },\n',
        "",
        "export long option",
    )
    down_text = _must_replace(
        down_text,
        '        c = getopt_long(argc, argv, "D:d:a:k:O:o:f:erNvVh",\n',
        '        c = getopt_long(argc, argv, "D:d:a:k:O:o:f:rNvVh",\n',
        "downloader getopt",
    )
    down_text = _must_replace(
        down_text,
        """        case 'e':
            exportPrivateKey = true;
            break;
        case 'r':
""",
        """        case 'r':
""",
        "export case",
    )
    down_text = _must_replace(
        down_text,
        """    if ((!acsmFile && !exportPrivateKey) || (outputDir && !outputDir[0]) ||
        (outputFile && !outputFile[0]))
""",
        """    if (!acsmFile || (outputDir && !outputDir[0]) ||
        (outputFile && !outputFile[0]))
""",
        "export required-args check",
    )
    down_text = _must_replace(
        down_text,
        """    if (exportPrivateKey)
    {
        if (acsmFile)
        {
            usage(argv[0]);
            return -1;
        }
    }
    else
    {
        if (!pathExists(acsmFile))
        {
            std::cout << "Error : " << acsmFile << " doesn't exists" << std::endl;
            ret = -1;
            goto end;
        }
    }
""",
        """    if (!pathExists(acsmFile))
    {
        std::cout << "Error : " << acsmFile << " doesn't exists" << std::endl;
        ret = -1;
        goto end;
    }
""",
        "export runtime branch",
    )
    downloader.write_text(down_text)

    readme = root / "README.md"
    readme_text = readme.read_text()
    readme_text = _must_replace(
        readme_text,
        "  * Remove DRM : _removeDRM()_\n",
        "",
        "readme removeDRM bullet",
    )
    readme_text = _must_replace(
        readme_text,
        "For those who want to remove DRM without adept_remove, you can export your private key and import it within [Calibre](https://calibre-ebook.com/) an its DeDRM plugin.\n\n\n",
        "",
        "readme key export paragraph",
    )
    readme_text = _must_replace(
        readme_text,
        """To export your private key (for DeDRM software):

    ./utils/acsmdownloader --export-private-key [-o adobekey_1.der]

To remove ADEPT DRM:

    ./utils/adept_remove <encryptedFile>

""",
        "",
        "readme export and remove commands",
    )
    readme.write_text(readme_text)

    man_activate = root / "utils" / "man" / "adept_activate.1"
    man_text = man_activate.read_text()
    anonymous_man = """.TP
\\fB\\-a\\fR|\\-\\-anonymous
Anonymous account, no need for username/password (Use it only with a DRM removal software)
"""
    if man_text.count(anonymous_man) != 2:
        raise SystemExit("unexpected adept_activate.1 anonymous sections")
    man_activate.write_text(man_text.replace(anonymous_man, ""))

    man_download = root / "utils" / "man" / "acsmdownloader.1"
    man_down = man_download.read_text()
    export_man = """.TP
\\fB\\-e\\fR|\\-\\-export\\-private\\-key
Export private key in DER format
"""
    man_down = _must_replace(man_down, export_man, "", "acsmdownloader man export")
    man_download.write_text(man_down)

    for relative in ("utils/adept_remove.cpp", "utils/man/adept_remove.1"):
        path = root / relative
        if path.exists():
            path.unlink()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} /path/to/libgourou")
    restrict(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
