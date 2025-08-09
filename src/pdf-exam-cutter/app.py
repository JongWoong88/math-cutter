import json
import fitz  # PyMuPDF
import zipfile
import base64
import io
from PIL import Image
import concurrent.futures # 병렬 처리를 위한 모듈
import numpy as np
import os

# 이미지 변환 후 고정할 가로 길이 (픽셀)
TARGET_IMAGE_WIDTH = 1000

# 세로축 분할 시 제거할 여백의 너비 (픽셀 단위)
VERTICAL_GUTTER_WIDTH = 5 # 예를 들어, 5픽셀 너비의 세로축을 제거한다고 가정

def trim_white_margins(image: Image.Image) -> Image.Image:
    """
    이미지의 상하좌우 흰색 여백을 제거하되, 5픽셀의 여백을 남깁니다. (NumPy 최적화)
    """
    if image.size[0] == 0 or image.size[1] == 0:
        return image

    img_array = np.array(image.convert('L'))
    WHITE_THRESHOLD = 240
    MARGIN = 5

    # 흰색이 아닌 픽셀의 좌표를 찾음
    non_white_pixels = np.where(img_array < WHITE_THRESHOLD)
    
    if non_white_pixels[0].size == 0: # 이미지가 모두 흰색인 경우
        return image

    # 상하좌우 경계를 한 번에 계산
    top = np.min(non_white_pixels[0])
    bottom = np.max(non_white_pixels[0])
    left = np.min(non_white_pixels[1])
    right = np.max(non_white_pixels[1])

    # 5픽셀 여백 추가
    crop_left = max(0, left - MARGIN)
    crop_top = max(0, top - MARGIN)
    crop_right = min(image.width, right + 1 + MARGIN)
    crop_bottom = min(image.height, bottom + 1 + MARGIN)

    return image.crop((crop_left, crop_top, crop_right, crop_bottom))

def find_first_horizontal_axis(image: Image.Image) -> int:
    """
    이미지 상단에서 첫 번째 가로선을 찾아, 그 선의 두께를 포함한 끝 Y좌표 바로 다음 좌표를 반환합니다. (NumPy 최적화)
    """
    if image.size[0] == 0 or image.size[1] == 0:
        return 0

    img_array = np.array(image.convert('L'))
    height, width = img_array.shape

    DARK_PIXEL_THRESHOLD = 100
    MIN_DARK_PIXEL_RATIO_FOR_LINE = 0.8
    min_dark_pixels_count = int(width * MIN_DARK_PIXEL_RATIO_FOR_LINE)
    search_start_y = min(20, height // 10)

    # 각 행의 어두운 픽셀 수를 한 번에 계산
    dark_pixel_counts = np.sum(img_array[search_start_y:, :] <= DARK_PIXEL_THRESHOLD, axis=1)
    
    # 가로줄 시작 Y 좌표 찾기
    line_start_y_relative = np.argmax(dark_pixel_counts >= min_dark_pixels_count)
    
    # np.argmax는 조건에 맞는 첫 번째 인덱스를 반환. 만약 조건에 맞는 행이 없으면 0을 반환.
    if dark_pixel_counts[line_start_y_relative] < min_dark_pixels_count:
        return 0 # 가로줄을 찾지 못함

    line_start_y = search_start_y + line_start_y_relative

    # 가로줄의 끝 Y 좌표 찾기 (두께 감안)
    MAX_BLANK_ROWS_IN_LINE = 5
    
    # line_start_y 이후의 행들에 대해 다시 어두운 픽셀 수 조건 확인
    is_line_row = (np.sum(img_array[line_start_y + 1:, :] <= DARK_PIXEL_THRESHOLD, axis=1) >= min_dark_pixels_count)
    
    # is_line_row는 [True, True, False, False, False, True, ...] 형태의 불리언 배열
    # 선이 끊기는 지점을 찾기 위해, 연속된 False가 MAX_BLANK_ROWS_IN_LINE보다 많은 곳을 찾음
    line_end_y = line_start_y
    blank_rows_count = 0
    for i, is_line in enumerate(is_line_row):
        if is_line:
            line_end_y = line_start_y + 1 + i
            blank_rows_count = 0
        else:
            blank_rows_count += 1
            if blank_rows_count > MAX_BLANK_ROWS_IN_LINE:
                break
    
    return line_end_y + 1

def find_vertical_split_axis(image: Image.Image) -> tuple[int, int]:
    """
    이미지에서 가장 어두운 세로축(분할선)의 X 좌표와 해당 축의 끝 Y 좌표를 찾습니다. (NumPy 최적화)
    """
    if image.size[0] == 0 or image.size[1] == 0:
        return image.size[0] // 2, image.size[1]

    img_array = np.array(image.convert('L'))
    height, width = img_array.shape

    # 1. 가장 어두운 세로줄의 X 좌표 찾기
    search_start_x = width // 4
    search_end_x = width * 3 // 4
    
    if search_start_x >= search_end_x: # 이미지가 너무 좁은 경우
        return width // 2, height

    # 각 열의 픽셀 값 합계를 한 번에 계산
    column_sums = np.sum(img_array[:, search_start_x:search_end_x], axis=0)
    
    # 가장 합계가 작은 열의 인덱스(상대적 위치)를 찾음
    split_x_relative = np.argmin(column_sums)
    split_x = search_start_x + split_x_relative

    # 2. 해당 세로줄(split_x)의 끝 Y 좌표 찾기 (60% 연속성 기준)
    band_width = 7
    DARK_PIXEL_THRESHOLD_FOR_AXIS_Y = 120
    MIN_DARK_PIXELS_IN_BAND = 2
    min_continuous_axis_length = int(height * 0.60)

    # split_x 주변 밴드의 픽셀들이 어두운지 여부를 나타내는 2D 불리언 배열 생성
    start_x = max(0, split_x - band_width // 2)
    end_x = min(width, split_x + band_width // 2 + 1)
    band_is_dark = img_array[:, start_x:end_x] < DARK_PIXEL_THRESHOLD_FOR_AXIS_Y
    
    # 각 행(Y)에서 밴드 내 어두운 픽셀의 수를 계산
    dark_pixels_per_row = np.sum(band_is_dark, axis=1)
    
    # 각 행이 유효한 축의 일부인지(어두운 픽셀 수가 기준 이상인지)를 나타내는 불리언 배열
    is_axis_row = dark_pixels_per_row >= MIN_DARK_PIXELS_IN_BAND

    # 하단부터 위로 스캔하며 연속된 True의 길이를 찾음
    # (이 부분은 순수 NumPy로 복잡하므로 루프를 유지하되, 픽셀 접근은 제거)
    current_continuous_length = 0
    potential_axis_end_y = height
    
    for y in range(height - 1, -1, -1):
        if is_axis_row[y]:
            current_continuous_length += 1
            if current_continuous_length == 1:
                potential_axis_end_y = y + 1
        else:
            if current_continuous_length >= min_continuous_axis_length:
                return split_x, potential_axis_end_y
            current_continuous_length = 0
    
    if current_continuous_length >= min_continuous_axis_length:
        return split_x, potential_axis_end_y

    return split_x, height # 유효한 축을 찾지 못하면 전체 높이 반환

def find_horizontal_split_points(image: Image.Image) -> list[int]:
    """
    이미지에서 행간 여백이 일정 비율을 넘어가면 수평 분할 지점(Y 좌표)을 찾습니다. (NumPy 최적화)
    """
    if image.size[0] == 0 or image.size[1] == 0:
        return []

    img_array = np.array(image.convert('L'))
    height, width = img_array.shape

    WHITE_THRESHOLD = 240
    MIN_GAP_HEIGHT_RATIO = 0.1
    min_gap_height = int(height * MIN_GAP_HEIGHT_RATIO)

    if min_gap_height == 0: return []

    # 각 행이 거의 흰색인지 한 번에 계산
    is_row_white = np.all(img_array >= WHITE_THRESHOLD, axis=1)

    split_points = []
    consecutive_white_rows = 0
    
    search_start_y = int(height * 0.05)
    search_end_y = int(height * 0.95)

    # 루프는 유지하되, 내부의 픽셀 접근 연산을 제거
    for y in range(search_start_y, search_end_y):
        if is_row_white[y]:
            consecutive_white_rows += 1
        else:
            if consecutive_white_rows >= min_gap_height:
                split_y = y - (consecutive_white_rows // 2)
                split_points.append(split_y)
            consecutive_white_rows = 0
            
    if consecutive_white_rows >= min_gap_height:
        split_y = search_end_y - (consecutive_white_rows // 2)
        split_points.append(split_y)

    return split_points

def is_mostly_white(image: Image.Image, threshold: float = 0.99) -> bool:
    """
    이미지의 흰색 픽셀 비율이 지정된 임계값을 초과하는지 확인합니다. (NumPy 최적화)
    """
    if image.size[0] == 0 or image.size[1] == 0:
        return True

    img_array = np.array(image.convert('L'))
    
    if img_array.size == 0:
        return True

    white_pixels = np.sum(img_array >= 240)
    total_pixels = img_array.size
            
    return (white_pixels / total_pixels) > threshold

def apply_color_inversion(image: Image.Image) -> Image.Image:
    """
    이미지에 색반전을 적용합니다. 흰색은 #31343a로, 검은색은 밝은 회색으로 변환합니다.
    """
    if image.size[0] == 0 or image.size[1] == 0:
        return image
    
    # RGBA 모드로 변환 (투명도 처리를 위해)
    img_rgba = image.convert('RGBA')
    img_array = np.array(img_rgba)
    
    # RGB 채널만 추출 (알파 채널 제외)
    rgb_array = img_array[:, :, :3].astype(np.float32)
    alpha_array = img_array[:, :, 3] if img_array.shape[2] == 4 else None
    
    # 색반전 적용 (255 - 원본값)
    inverted_rgb = 255 - rgb_array
    
    # 흰색(255,255,255)을 #31343a(49,52,58)로 매핑
    # 검은색(0,0,0)을 밝은 회색으로 매핑
    target_dark = np.array([49, 52, 58], dtype=np.float32)  # #31343a
    target_light = np.array([220, 220, 220], dtype=np.float32)  # 밝은 회색
    
    # 원본 픽셀의 밝기에 따라 target_dark와 target_light 사이에서 보간
    brightness = np.mean(rgb_array, axis=2, keepdims=True) / 255.0  # 0~1 범위
    
    # brightness가 높을수록(밝을수록) target_dark에 가깝게
    # brightness가 낮을수록(어둘수록) target_light에 가깝게
    final_rgb = target_light[np.newaxis, np.newaxis, :] * (1 - brightness) + \
                target_dark[np.newaxis, np.newaxis, :] * brightness
    
    final_rgb = np.clip(final_rgb, 0, 255).astype(np.uint8)
    
    # 알파 채널이 있으면 유지
    if alpha_array is not None:
        final_array = np.concatenate([final_rgb, alpha_array[:, :, np.newaxis]], axis=2)
        return Image.fromarray(final_array, 'RGBA').convert('RGB')
    else:
        return Image.fromarray(final_rgb, 'RGB')

def process_single_page(pdf_index: int, page_num: int, page_obj: fitz.Page, image_type: str = 'normal') -> list[tuple[str, bytes]]:
    """
    단일 PDF 페이지를 처리하여 분할된 이미지 데이터를 반환합니다.
    
    Args:
        pdf_index: PDF 파일 인덱스
        page_num: 페이지 번호
        page_obj: PyMuPDF 페이지 객체
        image_type: 'normal' 또는 'inverse'
    """
    log_prefix = f"[PDF-{pdf_index} Page-{page_num+1}]"
    print(f"{log_prefix} - 페이지 처리 시작.")
    
    processed_images = []
    try:
        # DPI 설정 없이 기본 해상도로 픽스맵 가져오기
        pix = page_obj.get_pixmap()
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        original_width, original_height = img.size
        print(f"{log_prefix} 원본 이미지 크기: {img.size}")
        
        # 이미지 가로 길이를 1000px로 조정 (세로 비율 유지)
        if original_width > 0: # 0으로 나누는 오류 방지
            new_height = int(original_height * (TARGET_IMAGE_WIDTH / original_width))
            img = img.resize((TARGET_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)
            print(f"{log_prefix} 리사이즈 후 크기: {img.size}")

        # 최종 이미지 최소 너비 (전체 페이지 너비의 20%)
        min_width_threshold = TARGET_IMAGE_WIDTH * 0.2

        # 1. 상하좌우 흰색 여백 제거
        img_before_trim = img.size
        img = trim_white_margins(img)
        print(f"{log_prefix} 1. 여백 제거 후 크기: {img_before_trim} -> {img.size}")

        # 2. 상단 양식 부분 제거를 위한 가로축 Y 좌표 감지 (두께 포함)
        crop_y = find_first_horizontal_axis(img)
        print(f"{log_prefix} 2. 상단 제거 Y좌표 감지: {crop_y}")
        
        # 3. 이미지 상단 자르기 (탐지된 가로줄 전체를 제거)
        if crop_y > 0:
            img_before_crop = img.size
            img = img.crop((0, crop_y, img.size[0], img.size[1]))
            print(f"{log_prefix} 3. 상단 제거 후 크기: {img_before_crop} -> {img.size}")
        
        # 4. 세로 분할을 위한 X 좌표 및 세로축 끝 Y 좌표 감지
        split_x, axis_bottom_y = find_vertical_split_axis(img)
        print(f"{log_prefix} 4. 세로 분할축(X, Y) 감지: ({split_x}, {axis_bottom_y})")
        
        # 5. 세로축 끝 지점 기준으로 이미지 하단 버리기
        if axis_bottom_y < img.size[1]:
            img_before_crop = img.size
            img = img.crop((0, 0, img.size[0], axis_bottom_y))
            print(f"{log_prefix} 5. 하단 제거 후 크기: {img_before_crop} -> {img.size}")

        # 6. 이미지 세로 2분할 (세로축 픽셀은 어디에도 포함되지 않음)
        left_crop_end_x = max(0, split_x - (VERTICAL_GUTTER_WIDTH // 2))
        right_crop_start_x = min(img.size[0], split_x + (VERTICAL_GUTTER_WIDTH // 2) + 1)

        left_half = img.crop((0, 0, left_crop_end_x, img.size[1]))
        right_half = None
        if right_crop_start_x < img.size[0]:
            right_half = img.crop((right_crop_start_x, 0, img.size[0], img.size[1]))
        
        print(f"{log_prefix} 6. 세로 2분할 완료. 왼쪽 크기: {left_half.size}, 오른쪽 크기: {right_half.size if right_half else 'None'}")
        
        # 7. 각 세로 분할 이미지에 대해 수평 분할 및 최종 여백 제거 및 흰색 이미지 필터링
        parts_to_process = []
        if left_half.size[0] > 0 and left_half.size[1] > 0:
            parts_to_process.append((left_half, "_part1"))
        if right_half and right_half.size[0] > 0 and right_half.size[1] > 0:
            parts_to_process.append((right_half, "_part2"))
        
        for current_img, part_suffix in parts_to_process:
            part_log_prefix = f"{log_prefix}{part_suffix}"
            print(f"{part_log_prefix} - 수평 분할 처리 시작.")
            if current_img.size[0] == 0 or current_img.size[1] == 0:
                continue

            horizontal_split_points = find_horizontal_split_points(current_img)
            print(f"{part_log_prefix} 수평 분할 지점: {horizontal_split_points}")
            
            current_y = 0
            sub_part_idx = 1
            
            split_segments = []
            if not horizontal_split_points:
                split_segments.append(current_img)
            else:
                for split_y in horizontal_split_points:
                    segment = current_img.crop((0, current_y, current_img.size[0], split_y))
                    split_segments.append(segment)
                    current_y = split_y
                # 마지막 조각 추가
                segment = current_img.crop((0, current_y, current_img.size[0], current_img.size[1]))
                split_segments.append(segment)

            for i, segment in enumerate(split_segments):
                final_cropped_img = trim_white_margins(segment)
                
                is_valid_width = final_cropped_img.size[0] > min_width_threshold
                is_valid_height = final_cropped_img.size[1] > 0
                is_not_white = not is_mostly_white(final_cropped_img)

                if is_valid_width and is_valid_height and is_not_white:
                    # 색상 처리 적용
                    if image_type == 'inverse':
                        final_cropped_img = apply_color_inversion(final_cropped_img)
                        print(f"{part_log_prefix} -> 색반전 처리 적용")
                    
                    file_name = f'pdf_{pdf_index}_page_{page_num + 1}{part_suffix}_sub{sub_part_idx}.png'
                    img_bytes = io.BytesIO()
                    final_cropped_img.save(img_bytes, format="PNG")
                    img_bytes.seek(0)
                    processed_images.append((file_name, img_bytes.read()))
                    print(f"{part_log_prefix} -> 최종 이미지 저장: {file_name}, 크기: {final_cropped_img.size}")
                else:
                    print(f"{part_log_prefix} -> 이미지 버림 (sub_{sub_part_idx}). 크기: {final_cropped_img.size}, 너비 유효: {is_valid_width}, 흰색 아님: {is_not_white}")
                sub_part_idx += 1

    except Exception as e:
        print(f"!!! {log_prefix} 처리 중 오류 발생: {str(e)}")
    
    print(f"{log_prefix} - 페이지 처리 완료. 총 {len(processed_images)}개 이미지 생성.")
    return processed_images

def handler(event, context):
    """
    여러 개의 Base64 인코딩된 PDF 파일을 입력받아 각 페이지를 PNG 이미지로 변환하고,
    상하좌우 흰색 여백 제거, 상단 양식 제거, 세로축 감지 2분할,
    세로축 끝 지점 기준 하단 버리기, 행간 여백에 따른 수평 분할을 수행하여
    하나의 ZIP 파일로 압축하여 Base64 인코딩된 문자열로 반환합니다.
    """
    # --- Secret Header 검증 로직 ---
    SECRET_VALUE = os.environ.get('CLOUDFRONT_SECRET_HEADER')
    headers = event.get('headers', {})
    
    # 헤더 이름은 소문자로 비교 (CloudFront/Lambda가 헤더 이름을 변경할 수 있음)
    received_secret = headers.get('x-origin-verify')

    if not SECRET_VALUE or received_secret != SECRET_VALUE:
        print("!!! 인증 실패: Secret Header 불일치 또는 누락")
        return {
            'statusCode': 403,
            'body': json.dumps('Forbidden: Invalid origin')
        }
    # --- Secret Header 검증 로직 끝 ---

    print("=== Lambda 함수 실행 시작 (인증 성공) ===")
    try:
        if isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event['body']
        
        pdf_files_b64 = body.get('files', [])
        file_name_with_ext = body.get('name', 'converted_images.pdf') # 기본값 설정
        file_name_without_ext = os.path.splitext(file_name_with_ext)[0]
        output_zip_name = f"{file_name_without_ext}.zip"
        image_type = body.get('type', 'normal') # 기본값: normal
        print(f"입력된 PDF 파일 수: {len(pdf_files_b64)}, 처리 타입: {image_type}")

        if not pdf_files_b64:
            print("오류: 입력된 파일이 없습니다.")
            return {
                'statusCode': 400,
                'body': json.dumps('No files provided.')
            }

        all_processed_images = []
        
        print("페이지 병렬 처리 시작...")
        # ThreadPoolExecutor를 사용하여 페이지 병렬 처리
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for i, pdf_b64 in enumerate(pdf_files_b64):
                try:
                    pdf_bytes = base64.b64decode(pdf_b64)
                    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
                    print(f"[PDF-{i}] 파일 열기 성공. 총 페이지: {len(pdf_document)}")
                    
                    for page_num in range(len(pdf_document)):
                        page = pdf_document.load_page(page_num)
                        futures.append(executor.submit(process_single_page, i, page_num, page, image_type))
                except Exception as e:
                    print(f"!!! [PDF-{i}] 파일 처리 중 오류 발생: {str(e)}")
                    continue
            
            print(f"총 {len(futures)}개 페이지를 스레드 풀에 제출 완료.")
            # 모든 스레드의 결과 수집
            for future in concurrent.futures.as_completed(futures):
                all_processed_images.extend(future.result())

        print(f"모든 페이지 처리 완료. 총 {len(all_processed_images)}개의 최종 이미지 수집.")
        
        # 모든 처리된 이미지를 ZIP 파일에 추가
        print("ZIP 파일 압축 시작...")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_name, img_bytes in all_processed_images:
                zipf.writestr(file_name, img_bytes)

        zip_buffer.seek(0)
        zip_b64 = base64.b64encode(zip_buffer.read()).decode('utf-8')
        print("ZIP 파일 압축 및 Base64 인코딩 완료.")

        print("=== Lambda 함수 성공적으로 실행 완료 ===")
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/zip',
                'Content-Disposition': f'attachment; filename="{output_zip_name}"'
            },
            'body': zip_b64,
            'isBase64Encoded': True
        }

    except Exception as e:
        print(f"!!! 핸들러에서 치명적인 오류 발생: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Internal server error: {str(e)}')
        }
