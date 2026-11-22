export const previewFields = [
  { id: 1, code: 'F03', name: 'Pasuquin Demo Plot', crop: 'Multiplier onion', area_ha: '0.45' },
  { id: 2, code: 'F07', name: 'Bacarra Demo Plot', crop: 'Multiplier onion', area_ha: '0.28' },
];

export const previewAdvisories = [
  {
    id: 1,
    field_code: 'F03',
    title: 'Check soil moisture before irrigating',
    body: 'Walk the upper and lower ends of the plot. Record where the soil still feels damp and share any uneven patches with your extension officer.',
    published_at: '2026-11-20T08:00:00+08:00',
  },
  {
    id: 2,
    field_code: 'F07',
    title: 'Document changes in leaf color',
    body: 'Take one photo of the entire row and another close-up of the affected leaves. Include the field code and when you first saw the change.',
    published_at: '2026-11-18T08:00:00+08:00',
  },
];

export const previewConversations = [
  {
    id: 1,
    field_code: 'F03',
    status: 'answered',
    messages: [
      { id: 1, direction: 'inbound', body: 'The leaves along the edge of F03 are turning yellow.', created_at: '2026-11-19T08:00:00+08:00' },
      { id: 2, direction: 'outbound', body: 'Please send a close-up of the leaves and tell me if the yellowing extends into the next row.', created_at: '2026-11-19T11:00:00+08:00' },
    ],
  },
  {
    id: 2,
    field_code: 'F07',
    status: 'awaiting_officer',
    messages: [
      { id: 3, direction: 'inbound', body: 'Water is pooling near the lower end of F07 after rain.', created_at: '2026-11-21T09:15:00+08:00' },
    ],
  },
];
