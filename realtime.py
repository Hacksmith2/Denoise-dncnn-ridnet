import streamlit as st
import cv2      
import os,urllib
import numpy as np    
import tensorflow as tf
import time

def main():

    selected_box = st.sidebar.selectbox(
        'Choose an option',
        ('Evaluate the model','View source code')
        )
        
    readme_text = st.markdown(get_file_content_as_string("README.md"))
    
    if selected_box == 'Evaluate the model':
        readme_text.empty()
        models()
    if selected_box=='View source code':
        readme_text.empty()
        st.code(get_file_content_as_string("realtime.py"))

        
@st.cache_data(show_spinner=False)
def get_file_content_as_string(path):
    url = 'https://raw.githubusercontent.com/Hacksmith2/Denoise-dncnn-ridnet/master/' + path
    response = urllib.request.urlopen(url)
    return response.read().decode("utf-8")


def models():

    st.title('Image denoising with deep learning models')
        
        
    st.write('\n')
    
    choice=st.sidebar.selectbox("Choose how to load image",["Use Existing Images","Browse Image"])
    
    if choice=="Browse Image":
      uploaded_file = st.sidebar.file_uploader("Choose a image file", type="jpg")

      if uploaded_file is not None:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        gt = cv2.imdecode(file_bytes, 1)
        prediction_ui(gt)
          
    if choice=="Use Existing Images":
    
      image_file_chosen = st.sidebar.selectbox('Select an existing image', get_list_of_images(),10)
      
      if image_file_chosen:
          imagespath=os.path.join(os.getcwd(),'images')
          gt=cv2.imread(os.path.join(imagespath,image_file_chosen))
          prediction_ui(gt)



def get_list_of_images():
    
    file_list = os.listdir(os.path.join(os.getcwd(),'images'))
    filenames=sorted([str(filename) for filename in file_list if str(filename).endswith('.jpg')])
    
    return filenames
    
def prediction_ui(gt):

    models_load_state=st.text('\n Loading models...')
    dncnn,ridnet=get_models()
    models_load_state.text('\n Models Loading Complete')

    dncnn_filesize,ridnet_filesize=get_filesizes()
    
    noise_level = st.sidebar.slider("Pick the noise level", 0, 45, 0)
          
    ground_truth,noisy_image,patches_noisy=get_image(gt,noise_level=noise_level)
    st.header('Input Image')
    st.markdown('Noise level : `%d` ( Noise level `0` will be same as the original image )'%(noise_level))
    st.image(noisy_image)

      
    model = st.sidebar.radio("Choose the denoising model",('DNCNN', 'RIDNET'),0)
    
    
    submit = st.sidebar.button('Denoise')
          
  
    if submit :
    
        if model=='DNCNN':
            progress_bar = st.progress(0)
            start=time.time()
            progress_bar.progress(20)
            denoised_image=predict_fun(dncnn,patches_noisy,gt)
            progress_bar.progress(80)
            end=time.time()
            st.header('Denoised image using DnCNN model')
            st.markdown('( Size of the model is : `%.3f` MB ) ( Time taken for prediction : `%.3f` seconds )'%(dncnn_filesize,(end-start)))
            st.image(denoised_image)     
            st.success('PSNR of denoised image : %.3f db  '%(PSNR(ground_truth,denoised_image)))
            progress_bar.progress(100)
            progress_bar.empty()
        
        elif model=='RIDNET':
        
            progress_bar = st.progress(0)
            start=time.time()
            progress_bar.progress(20)
            denoised_image=predict_fun(ridnet,patches_noisy,gt)
            progress_bar.progress(80)
            end=time.time()
            st.header('Denoised image using RIDNet model')
            st.markdown('( Size of the model is : `%.3f` MB ) ( Time taken for prediction : `%.3f` seconds )'%(ridnet_filesize,(end-start)))
            st.image(denoised_image)
            st.success('PSNR of denoised image : %.3f db  '%(PSNR(ground_truth,denoised_image)))        
            progress_bar.progress(100)
            progress_bar.empty() 



@st.cache_resource
def get_models():
    dncnn=tf.keras.models.load_model('dncnn.h5')
    ridnet=tf.keras.models.load_model('ridnet.h5')
    
    return dncnn,ridnet

  
@st.cache_data
def get_filesizes():
    
    dncnn_filesize=os.stat('dncnn.h5').st_size / (1024 * 1024)
    ridnet_filesize=os.stat('ridnet.h5').st_size / (1024 * 1024)
    return dncnn_filesize,ridnet_filesize
        
def get_patches(image):
    image=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
    height, width , channels= image.shape
    crop_sizes=[1]
    patch_size=40
    patches = []
    for crop_size in crop_sizes: 
        crop_h, crop_w = int(height*crop_size),int(width*crop_size)
        image_scaled = cv2.resize(image, (crop_w,crop_h), interpolation=cv2.INTER_CUBIC)
        for i in range(0, crop_h-patch_size+1, int(patch_size/1)):
            for j in range(0, crop_w-patch_size+1, int(patch_size/1)):
              x = image_scaled[i:i+patch_size, j:j+patch_size] 
              patches.append(x)
    return patches



def create_image_from_patches(patches,image_shape):
  image=np.zeros(image_shape)
  patch_size=patches.shape[1]
  p=0
  for i in range(0,image.shape[0]-patch_size+1,int(patch_size/1)):
    for j in range(0,image.shape[1]-patch_size+1,int(patch_size/1)):
      image[i:i+patch_size,j:j+patch_size]=patches[p]
      p+=1
  return np.array(image)

def get_image(gt,noise_level):

  patches=get_patches(gt)
  height, width , channels= gt.shape
  test_image=cv2.resize(gt, (width//40*40,height//40*40), interpolation=cv2.INTER_CUBIC)
  patches=np.array(patches)
  ground_truth=create_image_from_patches(patches,test_image.shape)

  patches = patches.astype('float32') /255.
  patches_noisy = patches+ tf.random.normal(shape=patches.shape,mean=0,stddev=noise_level/255) 
  patches_noisy = tf.clip_by_value(patches_noisy, clip_value_min=0., clip_value_max=1.)
  noisy_image=create_image_from_patches(patches_noisy,test_image.shape)
  
  return ground_truth/255.,noisy_image,patches_noisy
def predict_fun(model,patches_noisy,gt):

  height, width , channels= gt.shape
  gt=cv2.resize(gt, (width//40*40,height//40*40), interpolation=cv2.INTER_CUBIC)
  denoised_patches=model.predict(patches_noisy)
  denoised_patches=tf.clip_by_value(denoised_patches, clip_value_min=0., clip_value_max=1.)

  denoised_image=create_image_from_patches(denoised_patches,gt.shape)

  return denoised_image
    
  
def PSNR(gt, image, max_value=1):
    """"Function to calculate peak signal-to-noise ratio (PSNR) between two images."""
    height, width , channels= gt.shape
    gt=cv2.resize(gt, (width//40*40,height//40*40), interpolation=cv2.INTER_CUBIC)
    mse = np.mean((gt - image) ** 2)
    if mse == 0:
        return 100
    return 20 * np.log10(max_value / (np.sqrt(mse)))
    

if __name__ == "__main__":
    main()
