import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import '../providers/campaign_provider.dart';

class InputSection extends StatefulWidget {
  const InputSection({super.key});

  @override
  State<InputSection> createState() => _InputSectionState();
}

class _InputSectionState extends State<InputSection> {
  late final TextEditingController _contextController;
  late final TextEditingController _urlController;
  late final TextEditingController _usernameController;
  late final TextEditingController _passwordController;
  late final TextEditingController _roleController;

  bool _credentialsRequired = false;
  bool _roleRequired = false;

  @override
  void initState() {
    super.initState();
    final provider = context.read<CampaignProvider>();
    _contextController = TextEditingController(text: provider.rawContext);
    _urlController = TextEditingController(text: provider.productUrl);
    _usernameController = TextEditingController();
    _passwordController = TextEditingController();
    _roleController = TextEditingController();
  }

  @override
  void dispose() {
    _contextController.dispose();
    _urlController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _roleController.dispose();
    super.dispose();
  }

  Future<void> _analyzeUrl(BuildContext context) async {
    final provider = context.read<CampaignProvider>();
    final url = _urlController.text.trim();

    if (url.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please enter a website URL first")),
      );
      return;
    }

    if (_credentialsRequired &&
        (_usernameController.text.trim().isEmpty ||
            _passwordController.text.isEmpty)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Please enter both username and password"),
        ),
      );
      return;
    }

    if (_credentialsRequired &&
        _roleRequired &&
        _roleController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Please enter a role"),
        ),
      );
      return;
    }

    provider.setAnalyzingUrl(true);

    try {
      final dio = Dio();
      final formData = FormData.fromMap({
        'url': url,
        'credentials_required': _credentialsRequired,
        'username': _usernameController.text.trim(),
        'password': _passwordController.text,
        'role_required': _roleRequired,
        'role': _roleController.text.trim(),
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            _credentialsRequired
                ? "Analyzing authenticated website pages..."
                : "Analyzing website pages...",
          ),
        ),
      );

      final response = await dio.post(
        'http://localhost:8000/analyze_url',
        data: formData,
        options: Options(
          sendTimeout: const Duration(seconds: 180),
          receiveTimeout: const Duration(seconds: 180),
        ),
      );

      if (!context.mounted) return;

      if (response.statusCode == 200 && response.data['status'] == 'success') {
        final data = response.data['data'];
        final description = (data['description'] ?? '').toString().trim();
        final pageCount = data['page_count'];

        if (description.isEmpty) {
          throw Exception("No description returned from backend");
        }

        final existing = _contextController.text.trim();
        final updatedText = existing.isEmpty
            ? description
            : "$existing\n\nWebsite-derived description:\n$description";

        _contextController.text = updatedText;
        _contextController.selection = TextSelection.fromPosition(
          TextPosition(offset: updatedText.length),
        );
        provider.updateContext(updatedText);

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              pageCount != null
                  ? "✅ Website analyzed successfully ($pageCount pages)"
                  : "✅ Website analyzed and description added",
            ),
            backgroundColor: Colors.green,
          ),
        );
      } else {
        final message = response.data['message']?.toString() ?? 'Unknown error';
        throw Exception(message);
      }
    } on DioException catch (e) {
      if (!context.mounted) return;

      String message = "URL analysis failed";

      if (e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.connectionTimeout) {
        message =
            "URL analysis timed out. The site may be large, slow, or hard to crawl.";
      } else if (e.response != null &&
          e.response?.data is Map &&
          e.response?.data['message'] != null) {
        message = e.response?.data['message'].toString() ?? message;
      } else if (e.message != null) {
        message = e.message!;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("❌ $message"),
          backgroundColor: Colors.red,
        ),
      );
    } catch (e) {
      if (!context.mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("❌ URL analysis failed: $e"),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      provider.setAnalyzingUrl(false);
    }
  }

  Future<void> _generateCampaign(BuildContext context) async {
    final provider = context.read<CampaignProvider>();

    if (provider.rawContext.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Please enter a product description")),
      );
      return;
    }

    if (_credentialsRequired &&
        (_usernameController.text.trim().isEmpty ||
            _passwordController.text.isEmpty)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Please enter both username and password"),
        ),
      );
      return;
    }

    if (_credentialsRequired &&
        _roleRequired &&
        _roleController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Please enter a role"),
        ),
      );
      return;
    }

    provider.setGenerating(true);

    try {
      final dio = Dio();
      final formData = FormData.fromMap({
        'raw_context': provider.rawContext,
        'product_url': provider.productUrl,
        'generate_examples': provider.generateExamples,
        'use_rag': provider.useKnowledgeBase,
        'credentials_required': _credentialsRequired,
        'username': _usernameController.text.trim(),
        'password': _passwordController.text,
        'role_required': _roleRequired,
        'role': _roleController.text.trim(),
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Sending request to AI Marketing Agent...")),
      );

      final response = await dio.post(
        'http://localhost:8000/generate',
        data: formData,
        options: Options(
          sendTimeout: const Duration(seconds: 180),
          receiveTimeout: const Duration(seconds: 300),
        ),
      );

      if (!context.mounted) return;

      if (response.statusCode == 200 && response.data['status'] == 'success') {
        final data = response.data['data'];
        final rawOutputFiles = data['output_files'];
        final Map<String, String> outputFileUrls = {};

        if (rawOutputFiles is Map) {
          for (final entry in rawOutputFiles.entries) {
            final key = entry.key.toString();
            final value = entry.value;

            if (value is Map && value['download_url'] != null) {
              outputFileUrls[key] = value['download_url'].toString();
            }
          }
        }

        provider.updateOutputs(
          {
            'assessment': data['assessment'] ?? '# Assessment',
            'plan': data['plan'] ?? '# Plan',
            'playbooks': data['playbooks'] ?? '# Playbooks',
            'calendar': data['calendar'] ?? '# Calendar',
            'examples': data['examples'] ?? '# Examples',
          },
          newOutputFileUrls: outputFileUrls,
        );

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("✅ Campaign generated successfully!"),
            backgroundColor: Colors.green,
          ),
        );
      } else {
        final message = response.data['message']?.toString() ?? 'Unknown error';
        throw Exception(message);
      }
    } on DioException catch (e) {
      if (!context.mounted) return;

      String message = "Connection error. Is backend running?";

      if (e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.connectionTimeout) {
        message =
            "Campaign generation timed out. The request is taking too long.";
      } else if (e.response != null &&
          e.response?.data is Map &&
          e.response?.data['message'] != null) {
        message = e.response?.data['message'].toString() ?? message;
      } else if (e.message != null) {
        message = e.message!;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("❌ $message"),
          backgroundColor: Colors.red,
        ),
      );
    } catch (e) {
      if (!context.mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("❌ Connection error. Is backend running? $e"),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      provider.setGenerating(false);
    }
  }

  Future<void> _pickKbFiles(BuildContext context) async {
    final provider = context.read<CampaignProvider>();

    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['pdf', 'txt'],
      withData: true,
    );

    if (!context.mounted) return;
    if (result == null || result.files.isEmpty) return;

    final dio = Dio();
    final formData = FormData();

    for (final file in result.files) {
      if (file.bytes != null) {
        formData.files.add(
          MapEntry(
            "files",
            MultipartFile.fromBytes(
              file.bytes!,
              filename: file.name,
            ),
          ),
        );
      }
    }

    try {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Uploading KB files...")),
      );

      final response = await dio.post(
        'http://localhost:8000/upload_kb',
        data: formData,
      );

      if (!context.mounted) return;

      if (response.statusCode == 200) {
        for (final f in result.files) {
          provider.addKbFile(f.name);
        }
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("✅ KB Files saved successfully"),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (!context.mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("❌ Upload failed: $e"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _pickMediaFiles(BuildContext context) async {
    final provider = context.read<CampaignProvider>();

    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      withData: true,
    );

    if (!context.mounted) return;
    if (result == null || result.files.isEmpty) return;

    final dio = Dio();
    final formData = FormData();

    for (final file in result.files) {
      if (file.bytes != null) {
        formData.files.add(
          MapEntry(
            "files",
            MultipartFile.fromBytes(
              file.bytes!,
              filename: file.name,
            ),
          ),
        );
      }
    }

    try {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Uploading media files...")),
      );

      final response = await dio.post(
        'http://localhost:8000/upload_media',
        data: formData,
      );

      if (!context.mounted) return;

      if (response.statusCode == 200) {
        for (final f in result.files) {
          provider.addMediaFile(f.name);
        }
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("✅ Media saved successfully"),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (!context.mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("❌ Upload failed: $e"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Widget _buildUrlRow(BuildContext context, CampaignProvider provider) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 720;

        final urlField = TextField(
          controller: _urlController,
          decoration: const InputDecoration(
            labelText: "Product URL (Optional)",
            hintText: "https://yourproduct.com",
          ),
          onChanged: provider.updateProductUrl,
        );

        final credentialsCheckbox = CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          title: const Text("Credentials Required"),
          value: _credentialsRequired,
          onChanged: (value) {
            setState(() {
              _credentialsRequired = value ?? false;
              if (!_credentialsRequired) {
                _usernameController.clear();
                _passwordController.clear();
                _roleRequired = false;
                _roleController.clear();
              }
            });
          },
        );

        final usernameField = TextField(
          controller: _usernameController,
          decoration: const InputDecoration(
            labelText: "Username",
            hintText: "Enter username",
          ),
        );

        final passwordField = TextField(
          controller: _passwordController,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: "Password",
            hintText: "Enter password",
          ),
        );

        final roleCheckbox = CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          title: const Text("Additional Login Info Required"),
          value: _roleRequired,
          onChanged: (value) {
            setState(() {
              _roleRequired = value ?? false;
              if (!_roleRequired) {
                _roleController.clear();
              }
            });
          },
        );

        final roleField = TextField(
          controller: _roleController,
          decoration: const InputDecoration(
            labelText: "Role",
            hintText: "Enter role to select on the website",
          ),
        );

        final analyzeButton = SizedBox(
          width: isCompact ? double.infinity : null,
          height: 56,
          child: ElevatedButton(
            onPressed: provider.isAnalyzingUrl
                ? null
                : () => _analyzeUrl(context),
            child: provider.isAnalyzingUrl
                ? const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 2.5,
                        ),
                      ),
                      SizedBox(width: 10),
                      Text("Analyzing..."),
                    ],
                  )
                : const Text("Analyze URL"),
          ),
        );

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            urlField,
            const SizedBox(height: 8),
            credentialsCheckbox,
            if (_credentialsRequired) ...[
              const SizedBox(height: 8),
              usernameField,
              const SizedBox(height: 12),
              passwordField,
              const SizedBox(height: 8),
              roleCheckbox,
              if (_roleRequired) ...[
                const SizedBox(height: 8),
                roleField,
              ],
              const SizedBox(height: 8),
              const Text(
                "For best results, paste the direct login page URL when credentials are required. The backend will still try to find a login page automatically if the first page is not the login page.",
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
            ],
            const SizedBox(height: 12),
            if (isCompact)
              analyzeButton
            else
              Align(
                alignment: Alignment.centerLeft,
                child: analyzeButton,
              ),
          ],
        );
      },
    );
  }

  Widget _buildFileActionRow({
    required BuildContext context,
    required String uploadLabel,
    required IconData icon,
    required VoidCallback onUploadPressed,
    required VoidCallback onClearPressed,
  }) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 720;

        final uploadButton = SizedBox(
          width: isCompact ? double.infinity : null,
          child: ElevatedButton.icon(
            icon: Icon(icon),
            label: Text(uploadLabel),
            onPressed: onUploadPressed,
          ),
        );

        final clearButton = SizedBox(
          width: isCompact ? double.infinity : null,
          child: ElevatedButton(
            onPressed: onClearPressed,
            child: const Text("Clear"),
          ),
        );

        if (isCompact) {
          return Column(
            children: [
              uploadButton,
              const SizedBox(height: 8),
              clearButton,
            ],
          );
        }

        return Row(
          children: [
            Expanded(child: uploadButton),
            const SizedBox(width: 8),
            clearButton,
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CampaignProvider>();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "Campaign Brief",
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              "Describe your product, audience, goals & constraints",
              style: TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 20),
            Expanded(
              child: Scrollbar(
                thumbVisibility: true,
                child: SingleChildScrollView(
                  child: Padding(
                    padding: const EdgeInsets.only(right: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        TextField(
                          controller: _contextController,
                          maxLines: 8,
                          decoration: const InputDecoration(
                            labelText: "Product & Market Description",
                            alignLabelWithHint: true,
                            contentPadding: EdgeInsets.fromLTRB(12, 20, 12, 16),
                            hintText:
                                "Paste your product details, target audience, goals, constraints, etc...",
                          ),
                          onChanged: provider.updateContext,
                        ),
                        const SizedBox(height: 20),
                        _buildUrlRow(context, provider),
                        const SizedBox(height: 32),
                        const Text(
                          "Knowledge Base (Optional) (PDF/TXT)",
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 8),
                        _buildFileActionRow(
                          context: context,
                          uploadLabel: "Select KB Files",
                          icon: Icons.upload_file,
                          onUploadPressed: () => _pickKbFiles(context),
                          onClearPressed: provider.clearKbFiles,
                        ),
                        if (provider.kbFiles.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              "Saved KB: ${provider.kbFiles.join(', ')}",
                              style: const TextStyle(
                                fontSize: 12,
                                color: Colors.grey,
                              ),
                            ),
                          ),
                        const SizedBox(height: 24),
                        const Text(
                          "Product Media (Optional) (Images, Audio, Video)",
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 8),
                        _buildFileActionRow(
                          context: context,
                          uploadLabel: "Select Media",
                          icon: Icons.image,
                          onUploadPressed: () => _pickMediaFiles(context),
                          onClearPressed: provider.clearMediaFiles,
                        ),
                        if (provider.mediaFiles.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              "Saved Media: ${provider.mediaFiles.join(', ')}",
                              style: const TextStyle(
                                fontSize: 12,
                                color: Colors.grey,
                              ),
                            ),
                          ),
                        const SizedBox(height: 24),
                        SwitchListTile.adaptive(
                          contentPadding: EdgeInsets.zero,
                          title: const Text("Generate Example Posts"),
                          value: provider.generateExamples,
                          onChanged: provider.toggleExamples,
                          activeThumbColor: const Color(0xFF00F5FF),
                          activeTrackColor:
                              const Color(0xFF00F5FF).withValues(alpha: 0.5),
                        ),
                        SwitchListTile.adaptive(
                          contentPadding: EdgeInsets.zero,
                          title: const Text("Use Knowledge Base"),
                          value: provider.useKnowledgeBase,
                          onChanged: provider.toggleKnowledgeBase,
                          activeThumbColor: const Color(0xFF00F5FF),
                          activeTrackColor:
                              const Color(0xFF00F5FF).withValues(alpha: 0.5),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              height: 60,
              child: ElevatedButton(
                onPressed: provider.isGenerating
                    ? null
                    : () => _generateCampaign(context),
                child: provider.isGenerating
                    ? const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 3,
                            ),
                          ),
                          SizedBox(width: 12),
                          Text(
                            "Generating...",
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      )
                    : const Text(
                        "Generate Campaign",
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
