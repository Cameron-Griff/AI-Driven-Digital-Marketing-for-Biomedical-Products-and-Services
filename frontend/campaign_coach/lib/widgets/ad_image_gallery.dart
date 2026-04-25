import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/campaign_provider.dart';

class AdImageGallery extends StatefulWidget {
  const AdImageGallery({super.key});

  @override
  State<AdImageGallery> createState() => _AdImageGalleryState();
}

class _AdImageGalleryState extends State<AdImageGallery> {
  int _numImages = 1;
  bool _isGenerating = false;

  /// null = "All Posts". A non-null value is one of the parsed ## section keys.
  String? _selectedPostKey;

  // ---------------------------------------------------------------------------
  // Parsing
  // ---------------------------------------------------------------------------

  /// Splits the example-posts markdown into a map of { sectionTitle -> text }.
  /// Splits on `## ` headers; skips the top-level `# 4)` header line.
  Map<String, String> _parseExamplePosts(String examplesText) {
    final result = <String, String>{};
    String? currentKey;
    final buffer = StringBuffer();

    for (final line in examplesText.split('\n')) {
      final trimmed = line.trimLeft();

      if (trimmed.startsWith('## ')) {
        // Save previous section
        if (currentKey != null && buffer.isNotEmpty) {
          result[currentKey] = buffer.toString().trim();
        }
        currentKey = trimmed.substring(3).trim();
        buffer.clear();
        buffer.writeln(line);
      } else if (trimmed.startsWith('# ')) {
        // Top-level header — skip, don't add to any section
      } else {
        if (currentKey != null) {
          buffer.writeln(line);
        }
      }
    }

    // Save the last section
    if (currentKey != null && buffer.isNotEmpty) {
      result[currentKey] = buffer.toString().trim();
    }

    return result;
  }

  // ---------------------------------------------------------------------------
  // Guards
  // ---------------------------------------------------------------------------

  bool _hasExamplePosts(CampaignProvider provider) {
    final examples = (provider.outputs['examples'] ?? '').trim();
    final exampleFileUrl = (provider.outputFileUrls['examples'] ?? '').trim();

    if (exampleFileUrl.isEmpty) return false;

    return examples.isNotEmpty &&
        examples != '# 4) Example Posts\n\nNot found' &&
        examples != '# No examples yet';
  }

  // ---------------------------------------------------------------------------
  // Generation
  // ---------------------------------------------------------------------------

  Future<void> _generateAdImages() async {
    final provider = context.read<CampaignProvider>();
    final messenger = ScaffoldMessenger.of(context);

    if (!_hasExamplePosts(provider)) {
      messenger.showSnackBar(
        const SnackBar(
          content: Text('Generate campaign outputs with Example Posts first.'),
        ),
      );
      return;
    }

    setState(() => _isGenerating = true);

    try {
      final dio = Dio();

      // Decide which text to send — full examples or just the selected section
      final fullExamples = provider.outputs['examples'] ?? '';
      String sourceText = fullExamples;

      if (_selectedPostKey != null) {
        final parsed = _parseExamplePosts(fullExamples);
        sourceText = parsed[_selectedPostKey!] ?? fullExamples;
      }

      final formData = FormData.fromMap({
        'examples': sourceText,
        'raw_context': provider.rawContext,
        'num_images': _numImages,
      });

      final label = _selectedPostKey != null
          ? '"$_selectedPostKey"'
          : 'all example posts';

      messenger.showSnackBar(
        SnackBar(content: Text('Generating $_numImages image(s) for $label...')),
      );

      final response = await dio.post(
        'http://localhost:8000/generate_ad_images',
        data: formData,
        options: Options(
          sendTimeout: const Duration(seconds: 60),
          receiveTimeout: const Duration(seconds: 300),
        ),
      );

      if (!mounted) return;

      if (response.statusCode == 200 && response.data['status'] == 'success') {
        final rawImages = response.data['data']?['images'];

        if (rawImages is! List) {
          throw Exception('Backend did not return a valid image list.');
        }

        final imagePaths = rawImages.map((e) => e.toString()).toList();
        provider.addGeneratedImages(imagePaths);

        messenger.showSnackBar(
          SnackBar(
            content: Text('✅ Generated ${imagePaths.length} ad image(s).'),
            backgroundColor: Colors.green,
          ),
        );
      } else {
        final message =
            response.data['message']?.toString() ?? 'Unknown error';
        throw Exception(message);
      }
    } on DioException catch (e) {
      if (!mounted) return;

      String message = 'Image generation failed.';

      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.receiveTimeout) {
        message = 'Image generation timed out.';
      } else if (e.response != null &&
          e.response?.data is Map &&
          e.response?.data['message'] != null) {
        message = e.response?.data['message'].toString() ?? message;
      } else if (e.message != null) {
        message = e.message!;
      }

      messenger.showSnackBar(
        SnackBar(
          content: Text('❌ $message'),
          backgroundColor: Colors.red,
        ),
      );
    } catch (e) {
      if (!mounted) return;

      messenger.showSnackBar(
        SnackBar(
          content: Text('❌ Image generation failed: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) setState(() => _isGenerating = false);
    }
  }

  // ---------------------------------------------------------------------------
  // Image preview dialog
  // ---------------------------------------------------------------------------

  void _openImagePreview(String imageUrl) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return Dialog(
          backgroundColor: Colors.black,
          insetPadding: const EdgeInsets.all(24),
          child: Stack(
            children: [
              Positioned.fill(
                child: InteractiveViewer(
                  minScale: 0.8,
                  maxScale: 4.0,
                  child: Center(
                    child: Image.network(
                      imageUrl,
                      fit: BoxFit.contain,
                      filterQuality: FilterQuality.high,
                      alignment: Alignment.center,
                      errorBuilder: (context, error, stackTrace) {
                        return const Center(
                          child: Padding(
                            padding: EdgeInsets.all(24),
                            child: Text(
                              'Could not load image',
                              style: TextStyle(color: Colors.white),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ),
              ),
              Positioned(
                top: 8,
                right: 8,
                child: IconButton(
                  onPressed: () => Navigator.of(dialogContext).pop(),
                  icon: const Icon(Icons.close, color: Colors.white),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Image card
  // ---------------------------------------------------------------------------

  Widget _buildImageCard(String imageUrl) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF151525),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ClipRRect(
            borderRadius:
                const BorderRadius.vertical(top: Radius.circular(16)),
            child: InkWell(
              onTap: () => _openImagePreview(imageUrl),
              child: AspectRatio(
                aspectRatio: 1,
                child: Container(
                  color: Colors.black12,
                  padding: const EdgeInsets.all(12),
                  alignment: Alignment.center,
                  child: Image.network(
                    imageUrl,
                    fit: BoxFit.contain,
                    filterQuality: FilterQuality.high,
                    alignment: Alignment.center,
                    loadingBuilder: (context, child, loadingProgress) {
                      if (loadingProgress == null) return child;
                      return const Center(
                          child: CircularProgressIndicator());
                    },
                    errorBuilder: (context, error, stackTrace) {
                      return const Center(
                        child: Padding(
                          padding: EdgeInsets.all(16),
                          child: Text(
                            'Could not load image',
                            textAlign: TextAlign.center,
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: OutlinedButton(
              onPressed: () => _openImagePreview(imageUrl),
              child: const Text('Preview'),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<CampaignProvider>(context);
    final hasExamplePosts = _hasExamplePosts(provider);
    final examplesEnabled = provider.generateExamples;
    final canGenerateImages = examplesEnabled && hasExamplePosts;

    // Parse sections from examples markdown (empty map when no examples yet)
    final parsedSections = hasExamplePosts
        ? _parseExamplePosts(provider.outputs['examples'] ?? '')
        : <String, String>{};

    // If the previously selected key no longer exists (e.g. after a new
    // generation), reset it so the dropdown doesn't show a stale value.
    if (_selectedPostKey != null &&
        !parsedSections.containsKey(_selectedPostKey)) {
      Future.microtask(() {
        if (mounted) setState(() => _selectedPostKey = null);
      });
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ──────────────────────────────────────────────────────
            const Text(
              'Generate Visual Ads / Images',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),

            // ── Post selector ───────────────────────────────────────────────
            if (canGenerateImages && parsedSections.isNotEmpty) ...[
              const Text(
                'Generate image for:',
                style: TextStyle(fontWeight: FontWeight.w500),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String?>(
                value: _selectedPostKey,
                isExpanded: true,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                ),
                items: [
                  // "All" option at the top
                  const DropdownMenuItem<String?>(
                    value: null,
                    child: Text('All Posts (Full Examples)'),
                  ),
                  // One item per ## section
                  ...parsedSections.keys.map(
                    (key) => DropdownMenuItem<String?>(
                      value: key,
                      child: Text(key),
                    ),
                  ),
                ],
                onChanged: _isGenerating
                    ? null
                    : (value) {
                        setState(() {
                          _selectedPostKey = value;
                          // Sensible default: 1 image for a specific post,
                          // 2 when generating from all posts
                          _numImages = value == null ? 2 : 1;
                        });
                      },
              ),
              const SizedBox(height: 16),
            ],

            // ── Image count slider ──────────────────────────────────────────
            Row(
              children: [
                const Text('Number of images:'),
                const SizedBox(width: 12),
                Expanded(
                  child: Slider(
                    min: 1,
                    max: 4,
                    divisions: 3,
                    value: _numImages.toDouble(),
                    label: _numImages.toString(),
                    onChanged: (!canGenerateImages || _isGenerating)
                        ? null
                        : (value) {
                            setState(() => _numImages = value.round());
                          },
                  ),
                ),
                Text(_numImages.toString()),
              ],
            ),
            const SizedBox(height: 12),

            // ── Generate button ─────────────────────────────────────────────
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: (!canGenerateImages || _isGenerating)
                    ? null
                    : _generateAdImages,
                child: _isGenerating
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(
                        _selectedPostKey != null
                            ? 'Generate Image for "$_selectedPostKey"'
                            : 'Generate Ad Images',
                      ),
              ),
            ),
            const SizedBox(height: 20),

            // ── Status / gallery ────────────────────────────────────────────
            if (!examplesEnabled)
              const Text(
                'Must enable Example Posts output to generate images.',
                style: TextStyle(color: Colors.grey),
              )
            else if (!hasExamplePosts)
              const Text(
                'Generate campaign outputs first, then use the Example Posts '
                'section to create ad images.',
                style: TextStyle(color: Colors.grey),
              )
            else if (provider.generatedImagePaths.isNotEmpty)
              LayoutBuilder(
                builder: (context, constraints) {
                  int crossAxisCount = 1;
                  if (constraints.maxWidth >= 1100) {
                    crossAxisCount = 3;
                  } else if (constraints.maxWidth >= 700) {
                    crossAxisCount = 2;
                  }

                  return GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: provider.generatedImagePaths.length,
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: crossAxisCount,
                      mainAxisSpacing: 16,
                      crossAxisSpacing: 16,
                      childAspectRatio: 0.82,
                    ),
                    itemBuilder: (context, index) {
                      return _buildImageCard(
                          provider.generatedImagePaths[index]);
                    },
                  );
                },
              )
            else
              const Text(
                'Generated ads will appear here',
                style: TextStyle(color: Colors.grey),
              ),
          ],
        ),
      ),
    );
  }
}
