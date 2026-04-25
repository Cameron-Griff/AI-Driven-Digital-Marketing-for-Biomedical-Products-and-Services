import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../providers/campaign_provider.dart';
import 'ad_image_gallery.dart';
import 'chat_section.dart';

class OutputSection extends StatelessWidget {
  const OutputSection({super.key});

  static const String _backendBaseUrl = 'http://localhost:8000';

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<CampaignProvider>(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final tabHeight =
                (constraints.maxHeight * 0.45).clamp(320.0, 520.0);

            return SingleChildScrollView(
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Campaign Outputs',
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 16),
                    if (provider.outputFileUrls.isNotEmpty) ...[
                      Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: [
                          _buildDownloadButton(
                            context,
                            label: 'Download Plan',
                            relativeUrl: provider.outputFileUrls['plan'],
                          ),
                          _buildDownloadButton(
                            context,
                            label: 'Download Playbooks',
                            relativeUrl: provider.outputFileUrls['playbooks'],
                          ),
                          _buildDownloadButton(
                            context,
                            label: 'Download Calendar',
                            relativeUrl: provider.outputFileUrls['calendar'],
                          ),
                          if ((provider.outputFileUrls['examples'] ?? '')
                              .trim()
                              .isNotEmpty)
                            _buildDownloadButton(
                              context,
                              label: 'Download Examples',
                              relativeUrl: provider.outputFileUrls['examples'],
                            ),
                        ],
                      ),
                      const SizedBox(height: 16),
                    ],
                    SizedBox(
                      height: tabHeight,
                      child: DefaultTabController(
                        length: 4,
                        child: Column(
                          children: [
                            const TabBar(
                              tabs: [
                                Tab(text: 'Plan'),
                                Tab(text: 'Playbooks'),
                                Tab(text: 'Calendar'),
                                Tab(text: 'Examples'),
                              ],
                              labelColor: Color(0xFF00F5FF),
                              unselectedLabelColor: Colors.grey,
                              indicatorColor: Color(0xFF7B5EFF),
                            ),
                            const SizedBox(height: 16),
                            Expanded(
                              child: TabBarView(
                                children: [
                                  _buildMarkdown(
                                    provider.outputs['plan'] ?? '# No plan yet',
                                  ),
                                  _buildMarkdown(
                                    provider.outputs['playbooks'] ??
                                        '# No playbooks yet',
                                  ),
                                  _buildMarkdown(
                                    provider.outputs['calendar'] ??
                                        '# No calendar yet',
                                  ),
                                  _buildMarkdown(
                                    provider.outputs['examples'] ??
                                        '# No examples yet',
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    const AdImageGallery(),
                    const SizedBox(height: 24),
                    const ChatSection(),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildMarkdown(String content) {
    return SingleChildScrollView(
      child: MarkdownBody(data: content),
    );
  }

  Widget _buildDownloadButton(
    BuildContext context, {
    required String label,
    required String? relativeUrl,
  }) {
    final cleanedUrl = (relativeUrl ?? '').trim();
    final isEnabled = cleanedUrl.isNotEmpty;

    return OutlinedButton.icon(
      onPressed: !isEnabled
          ? null
          : () async {
              final uri = Uri.parse('$_backendBaseUrl$cleanedUrl');
              final success = await launchUrl(
                uri,
                mode: LaunchMode.platformDefault,
              );

              if (!context.mounted || success) return;

              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Could not open $label.'),
                  backgroundColor: Colors.red,
                ),
              );
            },
      icon: const Icon(Icons.download),
      label: Text(label),
    );
  }
}
