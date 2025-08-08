'''
PDF to Base64 Encoder

이 스크립트는 지정된 PDF 파일을 읽어 Base64 문자열로 인코딩한 후,
원본 파일 이름에 '_b64.txt'를 붙인 텍스트 파일로 저장합니다.

사용법:
1. 아래 `PDF_FILE_PATH` 변수에 변환할 PDF 파일의 경로를 입력합니다.
2. 터미널에서 `python encode_pdf.py` 명령을 실행합니다.
'''
import base64
import os

# --- 설정 --- #
# 여기에 변환하고 싶은 PDF 파일의 경로를 입력하세요.
PDF_FILE_PATH = "D:\\docker\\test\\sample.pdf" 
# --- 설정 끝 --- #

def encode_pdf_to_base64(pdf_path):
    """
    PDF 파일을 읽어 Base64로 인코딩하고 텍스트 파일로 저장합니다.
    """
    try:
        # 1. 파일 존재 여부 확인
        if not os.path.exists(pdf_path):
            print(f"[오류] 파일을 찾을 수 없습니다: '{pdf_path}'")
            return

        # 2. 출력 파일 경로 설정 (예: source.pdf -> source_b64.txt)
        base_name = os.path.splitext(pdf_path)[0]
        output_path = f"{base_name}_b64.txt"

        # 3. PDF 파일을 바이너리 모드로 읽기
        print(f"'{pdf_path}' 파일을 읽는 중...")
        with open(pdf_path, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()

        # 4. Base64로 인코딩
        print("Base64로 인코딩 하는 중...")
        base64_bytes = base64.b64encode(pdf_bytes)
        base64_string = base64_bytes.decode('utf-8')

        # 5. 인코딩된 문자열을 텍스트 파일에 저장
        print(f"'{output_path}' 파일로 저장하는 중...")
        with open(output_path, "w") as text_file:
            text_file.write(base64_string)

        print("\n--- 작업 완료 ---")
        print(f"성공적으로 변환하여 아래 경로에 저장했습니다:")
        print(f"-> {os.path.abspath(output_path)}")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")

if __name__ == "__main__":
    if PDF_FILE_PATH == "your_file.pdf":
        print("[주의] 스크립트의 `PDF_FILE_PATH` 변수를 실제 PDF 파일 경로로 수정해주세요.")
    else:
        encode_pdf_to_base64(PDF_FILE_PATH)
