import { Badge, Button, Group, Paper, Stack, Text, Title } from "@mantine/core";
import { RichTextEditor } from "@mantine/tiptap";
import Link from "@tiptap/extension-link";
import StarterKit from "@tiptap/starter-kit";
import { EditorContent, useEditor } from "@tiptap/react";
import { marked } from "marked";
import { useEffect, useMemo, useState } from "react";

type WikiPageCanvasProps = {
  title: string;
  slug: string | null;
  markdown: string;
  onApplyEditedStatement: (text: string) => void;
};

function markdownToHtml(markdown: string): string {
  const raw = marked.parse(markdown || "");
  return typeof raw === "string" ? raw : "";
}

function estimateReadingTimeMinutes(text: string): number {
  const words = text
    .replace(/[^\p{L}\p{N}\s'-]/gu, " ")
    .split(/\s+/)
    .filter(Boolean).length;
  if (words <= 0) return 0;
  return Math.max(1, Math.ceil(words / 220));
}

export default function WikiPageCanvas({
  title,
  slug,
  markdown,
  onApplyEditedStatement,
}: WikiPageCanvasProps) {
  const [editMode, setEditMode] = useState(false);
  const [seedVersion, setSeedVersion] = useState(0);
  const sourceHtml = useMemo(() => markdownToHtml(markdown), [markdown]);
  const plainText = useMemo(
    () =>
      markdown
        .replace(/`{1,3}[^`]*`{1,3}/g, " ")
        .replace(/[#>*_[\]()!-]/g, " ")
        .replace(/\s+/g, " ")
        .trim(),
    [markdown],
  );
  const wordCount = useMemo(() => (plainText ? plainText.split(/\s+/).filter(Boolean).length : 0), [plainText]);
  const readingMinutes = useMemo(() => estimateReadingTimeMinutes(plainText), [plainText]);
  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({
        openOnClick: true,
      }),
    ],
    content: sourceHtml,
    editable: editMode,
    immediatelyRender: false,
  });

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(editMode);
  }, [editMode, editor]);

  useEffect(() => {
    if (!editor) return;
    editor.commands.setContent(sourceHtml || "<p></p>", false);
    setSeedVersion((value) => value + 1);
  }, [editor, sourceHtml]);

  return (
    <Paper withBorder p="md" radius="md" className="wiki-canvas-card">
      <Group justify="space-between" align="flex-start" mb="sm">
        <Stack gap={2}>
          <Title order={6}>Wiki Page Canvas</Title>
          <Text size="xs" c="dimmed">
            {slug ? `${title} (${slug})` : title}
          </Text>
          <Group gap={6}>
            <Badge variant="light" color="violet">
              {wordCount} words
            </Badge>
            <Badge variant="light" color="indigo">
              {readingMinutes > 0 ? `~${readingMinutes} min read` : "no text"}
            </Badge>
          </Group>
        </Stack>
        <Group gap="xs">
          <Badge variant="light" color={editMode ? "orange" : "teal"}>
            {editMode ? "edit mode" : "read mode"}
          </Badge>
          <Button size="xs" variant="light" onClick={() => setEditMode((value) => !value)}>
            {editMode ? "Switch to read" : "Switch to edit"}
          </Button>
        </Group>
      </Group>

      {editor && (
        <RichTextEditor editor={editor} className="wiki-canvas-content">
          {editMode && (
            <RichTextEditor.Toolbar sticky stickyOffset={56}>
              <RichTextEditor.ControlsGroup>
                <RichTextEditor.Bold />
                <RichTextEditor.Italic />
                <RichTextEditor.Underline />
                <RichTextEditor.Strikethrough />
                <RichTextEditor.Code />
              </RichTextEditor.ControlsGroup>
              <RichTextEditor.ControlsGroup>
                <RichTextEditor.H1 />
                <RichTextEditor.H2 />
                <RichTextEditor.H3 />
                <RichTextEditor.Blockquote />
                <RichTextEditor.Hr />
              </RichTextEditor.ControlsGroup>
              <RichTextEditor.ControlsGroup>
                <RichTextEditor.BulletList />
                <RichTextEditor.OrderedList />
                <RichTextEditor.Link />
                <RichTextEditor.Unlink />
              </RichTextEditor.ControlsGroup>
            </RichTextEditor.Toolbar>
          )}
          <EditorContent editor={editor} key={`wiki-canvas-${seedVersion}`} />
        </RichTextEditor>
      )}

      <Group mt="sm" justify="space-between" align="center">
        <Text size="xs" c="dimmed">
          Use edit mode to prepare corrected statement text and pass it to moderation.
        </Text>
        <Button
          size="xs"
          onClick={() => {
            if (!editor) return;
            const text = editor.getText({ blockSeparator: "\n" }).trim();
            if (!text) return;
            onApplyEditedStatement(text);
          }}
        >
          Apply text to Approve form
        </Button>
      </Group>
    </Paper>
  );
}
