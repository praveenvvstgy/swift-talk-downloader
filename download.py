# python3 script
# put your cookie.txt next to the script and launch it from that working dir
#

import requests
from bs4 import BeautifulSoup
import os
import sys
from GoogleDriveWrapper import Folder
from cookies import loadCookies

CHUNKS_DIR = 'content'
VIDEOS_DIR = 'videos'

def appendPathComponent(base,addition):
    if not base[len(base)-1] == '/':
        base += '/'
    base+=addition
    return base

def downloadTextContent(url,cookies):
    print("downloading text content from "+url)
    resp = requests.get(url,cookies=cookies)
    return resp.text

def downloadContent(url,path,cookies=None):
    print("downloading "+url+" to "+path)
    file = open(path,"wb")
    resp = requests.get(url,stream=True,cookies=cookies)
    file.write(resp.content)
    file.close()

class Episode:
    def __init__(self,baseURL,relativeURL):
        self.baseURL = baseURL
        self.relativeURL = relativeURL
        self.fullName = self.getFullName()
        self.shortName = self.getShortName()
        self.ext = 'm2ts'
        self.gdriveUpload = False

    def __str__(self):
        return "Episode: " + self.fullName

    def __repr__(self):
        return self.__str__()

    def getFullName(self):
        components = self.relativeURL.split('/')
        return components[len(components)-1]

    def getShortName(self):
        components = self.fullName.split('-')
        return components[0]

    def makeEpisodePageURL(self,episode):
        pageURL = appendPathComponent(self.baseURL,episode)
        return pageURL

    def getFilesFromM3U(self,m3uContent):
        lines = m3uContent.split("\n")
        filenames = list(filter(lambda l: len(l) > 0 and not l[0] == '#', lines))
        return filenames

    def getBaseChunksSourceURL(self,markup):
        soup = BeautifulSoup(markup, "html.parser")
        video = soup.find("video")
        source = video.find("source")
        sourceURL = source["src"]
        baseSourceURL = sourceURL.rsplit("/", 1)[0]
        return baseSourceURL

    def getChunksDir(self):
        return os.path.join(os.getcwd(), CHUNKS_DIR, self.shortName)

    def downloadChunks(self,cookies):
        pageContent = downloadTextContent(self.makeEpisodePageURL(self.fullName), cookies=cookies)
        baseChunksSourceURL = self.getBaseChunksSourceURL(pageContent)
        m3uURL = appendPathComponent(baseChunksSourceURL, '1080p.m3u8')
        m3uContent = downloadTextContent(m3uURL, cookies=cookies)
        tsFiles = self.getFilesFromM3U(m3uContent)
        print("will download the following chunks: ", tsFiles)
        print("# of chunks: ", len(tsFiles))
        if len(tsFiles) < 20:
            print("skipping, probably cookie has expired")
            return

        dir = self.getChunksDir()
        os.system('mkdir -p ' + dir)

        files = os.listdir(dir)
        if len(files) >= len(tsFiles):
            print("skipping already downloaded")
            return

        for tsFile in tsFiles:
            tsFileURL = appendPathComponent(baseChunksSourceURL, tsFile)
            tsFilePath = os.path.join(dir, tsFile)
            downloadContent(tsFileURL, tsFilePath, cookies=cookies)

    def glueChunks(self):
        videoDir = self.getVideoDir()
        os.system('mkdir -p ' + videoDir)
        os.system('cat ' + self.getChunksDir() + '/*.ts > ' + self.getVideoFilePath())

    def getFileName(self, name):
        return name + '.' + self.ext

    def getVideoDir(self):
        return os.path.join(os.getcwd(), VIDEOS_DIR)

    def getVideoFilePath(self):
        fullFileName = self.getFileName(self.fullName)
        fullFileName = os.path.join(self.getVideoDir(), fullFileName)
        return fullFileName

    def renameExistingIfNeeded(self):
        fullFileName = self.getFileName(self.fullName)
        fullFilePath = self.getVideoFilePath()
        if os.path.exists(fullFilePath):
            return
        shortFileName = self.getFileName(self.shortName)
        shortFilePath = os.path.join(os.getcwd(), VIDEOS_DIR, shortFileName)
        if os.path.exists(shortFilePath):
            print("renaming " + shortFileName + " to " + fullFileName)
            os.rename(shortFilePath,fullFilePath)

    def isDownloaded(self):
        return os.path.exists(self.getVideoFilePath())

    def gdriveUploadIfNeeded(self):
        if self.gdriveUpload:
            f = Folder('SwiftTalk')
            print('uploading to google drive')
            f.upload(self.getVideoFilePath())

    def download(self,cookies):
        print("Downloading", self)
        self.renameExistingIfNeeded()
        if self.isDownloaded():
            print(self.fullName + ' is already downloaded')
            return
        self.downloadChunks(cookies)
        self.glueChunks()
        self.gdriveUploadIfNeeded()

def saveUTF8Text(text,path):
    file = open(path, "wb")
    file.write(text.encode("utf-8"))
    file.close()

def loadUTF8Text(path):
    file = open(path,"rb")
    content = file.read()
    file.close()
    return content.decode("utf-8")

def parseEpisodes(baseURL,cookies):
    episodesPage = downloadTextContent(baseURL,cookies)
    soup = BeautifulSoup(episodesPage, "html.parser")
    episodes = []
    for h3 in soup.find_all('h3'):
        a = h3.find('a')
        if a is None:
            return None
        relativeURL = a['href']
        episode = Episode(baseURL,relativeURL)
        episodes.append(episode)
    return episodes

def main():
    baseURL = "https://talk.objc.io/episodes/"
    cookieFileName = os.path.join(os.getcwd(), 'cookies.txt')
    cookies = loadCookies(cookieFileName)
    episodes = parseEpisodes(baseURL, cookies)

    if episodes is None or len(episodes) == 0:
        print("Error parsing episodes, check your cookies")
        return

# TODO: use some nice argument parsing lib, like getopt
    if '--gdrive-upload' in sys.argv:
        for episode in episodes:
            episode.gdriveUpload = True

    if '--last' in sys.argv or '--latest' in sys.argv:
        print("Downloading last episode only")
        episodes[0].download(cookies)
    elif '-e' in sys.argv:
        argInd = sys.argv.index('-e')
        ep = sys.argv[argInd+1]
        print("Downloading episode",ep)
        for episode in episodes:
            if ep in episode.fullName:
                episode.download(cookies)
                break
    else:
        for episode in episodes:
            episode.download(cookies)


if __name__ == "__main__":
    main()
