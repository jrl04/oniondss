import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

const dateLabel = date => new Date(date).toLocaleDateString();
const initials = name => name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();

export function FarmerProfile({ farmer, fields, onFields, onJournal }) {
  const crops = [...new Set(fields.map(field => field.crop).filter(Boolean))].join(', ');
  return (
    <View style={styles.profile}>
      <View style={styles.avatar}><Text style={styles.avatarText}>{initials(farmer.name)}</Text></View>
      <Text accessibilityRole="header" style={styles.name}>{farmer.name}</Text>
      {!!farmer.location && <Text style={styles.profileText}>{farmer.location}</Text>}
      {!!farmer.bio && <Text style={styles.profileText}>{farmer.bio}</Text>}
      {!!crops && <Text style={styles.profileText}>{crops}</Text>}
      <View style={styles.profileActions}>
        <Pressable accessibilityRole="button" style={styles.profileButton} onPress={onFields}>
          <Text style={styles.strong}>{fields.length} registered {fields.length === 1 ? 'field' : 'fields'}</Text>
        </Pressable>
        <Pressable accessibilityRole="button" style={styles.profileButton} onPress={onJournal}>
          <Text style={styles.strong}>Open journal</Text>
        </Pressable>
      </View>
    </View>
  );
}

export function FarmerJournal({ farmer, notes, addNote, advisories, preview }) {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [composing, setComposing] = useState(false);
  const [expanded, setExpanded] = useState({});
  const posts = [
    ...notes.map(note => ({ ...note, key: `note-${note.id}`, label: farmer.name })),
    ...advisories.map(advisory => ({
      ...advisory,
      key: `advisory-${advisory.id}`,
      label: preview ? 'Sample advisory' : 'Field advisory',
    })),
  ].sort((first, second) => new Date(second.published_at) - new Date(first.published_at));

  function publish() {
    if (!title.trim() || !body.trim()) return;
    addNote({ title: title.trim(), body: body.trim(), published_at: new Date().toISOString() });
    setTitle('');
    setBody('');
    setComposing(false);
  }

  return (
    <>
      {preview && (
        <Pressable accessibilityRole="button" style={styles.action} onPress={() => setComposing(value => !value)}>
          <Text style={styles.strong}>{composing ? 'Close editor' : 'Write a sample post'}</Text>
        </Pressable>
      )}
      {composing && (
        <View style={styles.post}>
          <Text style={styles.meta}>Sample posts reset when you exit preview.</Text>
          <TextInput accessibilityLabel="Post title" placeholder="Post title" value={title} onChangeText={setTitle} maxLength={120} style={styles.input} />
          <TextInput accessibilityLabel="Post body" placeholder="What happened in the field?" value={body} onChangeText={setBody} maxLength={1500} multiline style={[styles.input, styles.multiline]} />
          <Pressable accessibilityRole="button" disabled={!title.trim() || !body.trim()} style={styles.action} onPress={publish}>
            <Text style={[styles.strong, (!title.trim() || !body.trim()) && styles.meta]}>Add to sample journal</Text>
          </Pressable>
        </View>
      )}
      {!posts.length && <Text style={styles.meta}>No field advisories have been published yet.</Text>}
      {posts.map(post => (
        <View key={post.key} style={styles.post}>
          <Text style={styles.meta}>{[post.label, post.field_code, dateLabel(post.published_at)].filter(Boolean).join(' · ')}</Text>
          <Text accessibilityRole="header" style={styles.postTitle}>{post.title}</Text>
          <Text numberOfLines={expanded[post.key] ? undefined : 2} style={styles.body}>{post.body}</Text>
          <Pressable accessibilityRole="button" accessibilityState={{ expanded: !!expanded[post.key] }} onPress={() => setExpanded(previous => ({ ...previous, [post.key]: !previous[post.key] }))}>
            <Text style={styles.link}>{expanded[post.key] ? 'Show less' : 'Read post'}</Text>
          </Pressable>
        </View>
      ))}
    </>
  );
}

const styles = StyleSheet.create({
  profile: { backgroundColor: '#244e3a', borderRadius: 20, padding: 22, marginBottom: 16 },
  avatar: { width: 58, height: 58, borderRadius: 29, justifyContent: 'center', alignItems: 'center', backgroundColor: '#e9edcf' },
  avatarText: { color: '#244e3a', fontSize: 22, fontWeight: '800' },
  name: { color: '#fff', fontSize: 28, fontWeight: '800', marginTop: 12 },
  profileText: { color: '#e4eedf', fontSize: 15, lineHeight: 23, marginTop: 5 },
  profileActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 18 },
  profileButton: { backgroundColor: '#e9edcf', borderRadius: 10, padding: 10 },
  post: { backgroundColor: '#fff', borderColor: '#dce4d8', borderWidth: 1, borderRadius: 16, padding: 16, marginBottom: 12 },
  meta: { color: '#526356', fontSize: 13, lineHeight: 20 },
  postTitle: { color: '#24342b', fontSize: 20, fontWeight: '800', marginTop: 6 },
  body: { color: '#24342b', fontSize: 15, lineHeight: 23, marginTop: 7 },
  strong: { color: '#244e3a', fontWeight: '800' },
  link: { color: '#244e3a', fontWeight: '800', paddingVertical: 10 },
  action: { alignSelf: 'flex-start', backgroundColor: '#e6eedf', borderRadius: 10, padding: 11, marginBottom: 12 },
  input: { color: '#24342b', borderColor: '#dce4d8', borderWidth: 1, borderRadius: 10, padding: 11, marginTop: 8 },
  multiline: { minHeight: 96, textAlignVertical: 'top', marginBottom: 12 },
});
