from PyQt4.Qt import *
from redditData import DownloadType

class Downloader(QObject):

    finished = pyqtSignal()

    def __init__(self, rddtScraper, validRedditors, queue):
        super().__init__()
        self.rddtScraper = rddtScraper
        self.validRedditors = validRedditors
        self.queue = queue
        self.userPool = QThreadPool()
        self.userPool.setMaxThreadCount(4)

    @pyqtSlot()
    def run(self):
        if len(self.validRedditors) > 0:
            for user, redditor in self.validRedditors:
                userWorker = UserWorker(self.rddtScraper, user, redditor, self.queue)
                self.userPool.start(userWorker)
            self.userPool.waitForDone()
        self.rddtScraper.saveState()
        self.finished.emit()

class UserWorker(QRunnable):
    def __init__(self, rddtScraper, user, redditor, queue):
        super().__init__()

        self.rddtScraper = rddtScraper
        self.user = user
        self.redditor = redditor
        self.queue = queue
        self.imagePool = QThreadPool()
        self.imagePool.setMaxThreadCount(3)

    def run(self):
        userName = self.user.name
        self.queue.put("Starting download for " + userName + "\n")
        self.rddtScraper.makeDirectoryForUser(userName)
        # Temporary
        refresh = None
        submitted = self.redditor.get_submitted(limit=refresh)
        posts = self.rddtScraper.getValidPosts(submitted, self.user)
        for post in posts:
            images = self.rddtScraper.getImages(post, self.user)
            for image in images:
                if image is not None:
                    imageWorker = ImageWorker(image, self.user, self.rddtScraper.avoidDuplicates, self.queue)
                    self.imagePool.start(imageWorker)
            self.imagePool.waitForDone()


class ImageWorker(QRunnable):
    def __init__(self, image, user, avoidDuplicates, queue):
        super().__init__()

        self.image = image
        self.user = user
        self.avoidDuplicates = avoidDuplicates
        self.queue = queue

    def run(self):
        allExternalDownloads = set([])
        for redditPostURL in self.user.externalDownloads:
            allExternalDownloads = allExternalDownloads.union(allExternalDownloads, self.user.externalDownloads.get(redditPostURL))
        if (not self.avoidDuplicates) or (self.avoidDuplicates and self.image.URL not in allExternalDownloads):
            if self.user.redditPosts.get(self.image.redditPostURL) is None:  # Add 1 representative picture for this post, even if it is an album with multiple pictures
                self.user.redditPosts[self.image.redditPostURL] = self.image.savePath
            if self.user.externalDownloads.get(self.image.redditPostURL) is None:
                self.user.externalDownloads[self.image.redditPostURL] = {self.image.URL}
            else:
                self.user.externalDownloads.get(self.image.redditPostURL).add(self.image.URL)
            self.image.download()
            self.queue.put('Saved %s' % self.image.savePath + "\n")