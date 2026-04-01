/**
 * errorMessages.js — Phase 7.5
 * Maps backend error strings → user-friendly messages per language.
 * Falls back to the raw message if no mapping found.
 */

const ERROR_MAP = {
  en: {
    'Company not found':                      'Company not found. Please select a valid company.',
    'No successful uploads found':            'No data uploaded yet. Please upload a Trial Balance first.',
    'Could not build financial statements':   'Could not generate statements — the normalized file may be missing. Try re-uploading.',
    'No month columns detected':              'No month columns found in the file. Check the format guide.',
    'Missing required columns':               'Required columns are missing. Expected: account_code, account_name, debit, credit.',
    'validation_empty':                       'The file is empty or contains no valid data rows.',
    'File is empty':                          'The uploaded file is empty.',
    'File too large':                         'File exceeds the 20 MB limit. Please reduce the file size.',
    'Unsupported file type':                  'Unsupported file format. Please upload .xlsx, .xls, or .csv.',
    'Upload not found':                       'Upload record not found.',
    'No normalized file':                     'Processed data not found on server. Please re-upload the file.',
    'Annual wide file parsed to zero rows':   'No valid data rows found in annual file. Check that account codes are present.',
    'Period already exists':                  'A upload for this period already exists for this company.',
  },
  ar: {
    'Company not found':                      'الشركة غير موجودة. يرجى اختيار شركة صحيحة.',
    'No successful uploads found':            'لم يتم رفع أي بيانات بعد. يرجى رفع ميزان المراجعة أولاً.',
    'Could not build financial statements':   'تعذّر إنشاء القوائم المالية — قد يكون الملف الموحّد مفقوداً. حاول إعادة الرفع.',
    'No month columns detected':              'لم يتم اكتشاف أعمدة الأشهر في الملف. راجع دليل التنسيق.',
    'Missing required columns':               'أعمدة مطلوبة مفقودة. المتوقع: رقم الحساب، اسم الحساب، مدين، دائن.',
    'validation_empty':                       'الملف فارغ أو لا يحتوي على صفوف بيانات صحيحة.',
    'File is empty':                          'الملف المرفوع فارغ.',
    'File too large':                         'الملف يتجاوز حد 20 ميجابايت.',
    'Unsupported file type':                  'نوع الملف غير مدعوم. يرجى رفع .xlsx أو .xls أو .csv.',
    'Upload not found':                       'سجل الرفع غير موجود.',
    'No normalized file':                     'البيانات المعالجة غير موجودة على الخادم. يرجى إعادة الرفع.',
    'Annual wide file parsed to zero rows':   'لم يتم العثور على صفوف بيانات في الملف السنوي. تأكد من وجود أرقام الحسابات.',
    'Period already exists':                  'يوجد رفع لهذه الفترة مسبقاً لهذه الشركة.',
  },
  tr: {
    'Company not found':                      'Şirket bulunamadı. Lütfen geçerli bir şirket seçin.',
    'No successful uploads found':            'Henüz veri yüklenmedi. Lütfen önce bir mizan yükleyin.',
    'Could not build financial statements':   'Mali tablolar oluşturulamadı — işlenmiş dosya eksik olabilir. Yeniden yüklemeyi deneyin.',
    'No month columns detected':              'Dosyada ay sütunu bulunamadı. Format kılavuzunu kontrol edin.',
    'Missing required columns':               'Gerekli sütunlar eksik. Beklenen: hesap_kodu, hesap_adı, borç, alacak.',
    'validation_empty':                       'Dosya boş veya geçerli veri satırı içermiyor.',
    'File is empty':                          'Yüklenen dosya boş.',
    'File too large':                         'Dosya 20 MB sınırını aşıyor.',
    'Unsupported file type':                  'Desteklenmeyen dosya formatı. Lütfen .xlsx, .xls veya .csv yükleyin.',
    'Upload not found':                       'Yükleme kaydı bulunamadı.',
    'No normalized file':                     'İşlenmiş veriler sunucuda bulunamadı. Lütfen dosyayı yeniden yükleyin.',
    'Annual wide file parsed to zero rows':   'Yıllık dosyada geçerli veri satırı bulunamadı. Hesap kodlarının mevcut olduğunu kontrol edin.',
    'Period already exists':                  'Bu şirket için bu döneme ait bir yükleme zaten mevcut.',
  },
}

/**
 * Map a backend error message to a user-friendly string.
 * @param {string} rawError  — raw error text from API
 * @param {string} lang      — current language code
 * @returns {string}
 */
export function mapError(rawError, lang = 'en') {
  if (!rawError) return ''
  const map = ERROR_MAP[lang] || ERROR_MAP.en
  for (const [key, friendly] of Object.entries(map)) {
    if (rawError.includes(key)) return friendly
  }
  return rawError   // fallback to raw message
}
