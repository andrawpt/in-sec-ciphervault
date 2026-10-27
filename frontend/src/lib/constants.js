export const APP_NAME = 'Safe Report'
export const OFFICER_UNIT = 'Task Force'

export const CATEGORIES = [
  { value: 'kekerasan_seksual', label: 'Sexual violence', hint: 'Non-consensual sexual touch, coercion, or acts' },
  { value: 'pelecehan_seksual', label: 'Verbal/non-physical sexual harassment', hint: 'Comments, catcalling, gestures, or sexually suggestive messages' },
  { value: 'kbgo', label: 'Online gender-based violence (OGBV)', hint: 'Dissemination of intimate photos/videos, sextortion, recording without consent' },
  { value: 'perundungan', label: 'Bullying', hint: 'Repeated mockery, ostracism, or intimidation' },
  { value: 'perundungan_siber', label: 'Cyberbullying', hint: 'Insults, doxing, fake accounts, or content meant to humiliate' },
  { value: 'kekerasan_fisik', label: 'Physical violence', hint: 'Hitting, assault, or damaging victim property' },
  { value: 'kekerasan_psikis', label: 'Psychological violence', hint: 'Threats, extortion, or degradation of dignity' },
  { value: 'lainnya', label: 'Other', hint: 'Other forms of violence in the campus environment' },
]
export const categoryLabel = (v) => CATEGORIES.find((c) => c.value === v)?.label ?? v

export const STATUS = {
  diterima: { label: 'Received', cls: 'bg-slate-100 text-slate-700 ring-slate-300' },
  diverifikasi: { label: 'Verified', cls: 'bg-sky-50 text-sky-700 ring-sky-200' },
  ditindaklanjuti: { label: 'In Progress', cls: 'bg-amber-50 text-amber-800 ring-amber-200' },
  selesai: { label: 'Resolved', cls: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  ditolak: { label: 'Rejected', cls: 'bg-red-50 text-red-700 ring-red-200' },
}
export const STATUS_FLOW = ['diterima', 'diverifikasi', 'ditindaklanjuti', 'selesai']

export const CIPHERS = [
  { value: 'AES-256-GCM', short: 'AES', desc: 'AES-256, GCM mode (default)' },
  { value: 'DES-CBC-HMAC', short: 'DES', desc: 'DES, CBC mode + HMAC-SHA256' },
  { value: 'RC4-HMAC', short: 'RC4', desc: 'RC4 (drop 3072) + HMAC-SHA256' },
]

export const FILE_RULES = {
  ktp: { accept: '.jpg,.jpeg,.png,.pdf', maxMb: 10, label: 'JPG, PNG, or PDF, max 10 MB' },
  dokumen: {
    accept: '.jpg,.jpeg,.png,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.txt,.eml',
    maxMb: 25,
    label: 'Image (JPG/PNG), PDF, Word, Excel, PowerPoint, TXT, or EML, max 25 MB',
  },
  video: { accept: '.mp4,.mov,.webm,.mkv', maxMb: 200, label: 'MP4, MOV, WEBM, or MKV, max 200 MB' },
}

export const KYC = {
  belum: { label: 'ID not yet uploaded', cls: 'bg-slate-100 text-slate-700 ring-slate-300' },
  menunggu: { label: 'Pending verification', cls: 'bg-sky-50 text-sky-700 ring-sky-200' },
  terverifikasi: { label: 'Verified', cls: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  ditolak: { label: 'Rejected', cls: 'bg-red-50 text-red-700 ring-red-200' },
  verifikasi_ulang: { label: 'Re-verification required', cls: 'bg-amber-50 text-amber-800 ring-amber-200' },
}
