import axios from 'axios';

export const PERSON_PHOTO_CHUNK_SIZE = 512 * 1024;

export async function uploadPersonPhoto({ file, personId, API, getAuthHeaders, onProgress = () => {} }) {
  if (!file) return null;
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    throw new Error('Usa una imagen JPG, PNG o WebP.');
  }
  if (file.size > 5 * 1024 * 1024) throw new Error('La fotografía no puede superar 5 MB.');
  const totalChunks = Math.ceil(file.size / PERSON_PHOTO_CHUNK_SIZE);
  const init = await axios.post(
    `${API}/api/core/persons/${personId}/photo/uploads`,
    { content_type: file.type, total_size: file.size, total_chunks: totalChunks },
    getAuthHeaders()
  );
  for (let index = 0; index < totalChunks; index += 1) {
    const chunk = file.slice(
      index * PERSON_PHOTO_CHUNK_SIZE,
      Math.min((index + 1) * PERSON_PHOTO_CHUNK_SIZE, file.size)
    );
    await axios.put(
      `${API}/api/core/persons/${personId}/photo/uploads/${init.data.upload_id}/chunks/${index}`,
      chunk,
      {
        ...getAuthHeaders(),
        headers: { ...getAuthHeaders().headers, 'Content-Type': 'application/octet-stream' },
      }
    );
    onProgress(Math.round(((index + 1) / totalChunks) * 90));
  }
  const completed = await axios.post(
    `${API}/api/core/persons/${personId}/photo/uploads/${init.data.upload_id}/complete`,
    {},
    getAuthHeaders()
  );
  onProgress(100);
  return completed.data;
}
