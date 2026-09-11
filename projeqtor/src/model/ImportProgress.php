<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU Affero General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/* ============================================================================
 * Habilitation defines right to the application for a menu and a profile.
 */

require_once('_securityCheck.php');

class ImportProgress {
  
  private static function sessionKey($idUser) {
    if (is_object($idUser)) {
      $idUser = $idUser->id;
    }
    return 'importProgress_' . $idUser;
  }
  
  private static function ensureSessionStarted() {
    if (session_status() !== PHP_SESSION_ACTIVE) {
      session_start();
    }
  }
  
  public static function start($idUser) {
    self::ensureSessionStarted();
    $_SESSION[self::sessionKey($idUser)] = array(
        'current' => 0,
        'total'  => 0,
        'status' => 'running',
        'startTime' => time(),
    );
    session_write_close();
  }
  
  public static function update($idUser, $current, $total = null) {
    self::ensureSessionStarted();
    $key = self::sessionKey($idUser);
    if (isset($_SESSION[$key])) {
      $_SESSION[$key]['current'] = $current;
      if ($total !== null) {
        $_SESSION[$key]['total'] = $total;
      }
    }
    session_write_close();
  }
  
  public static function finish($idUser, $resultHtml, $class = null, $fileName = null, $status = 'done') {
    self::ensureSessionStarted();
    $key = self::sessionKey($idUser);
    if (isset($_SESSION[$key])) {
      $_SESSION[$key]['status'] = $status;
    }
    session_write_close();
    
    $dir = self::getResultDir();
    if (!file_exists($dir)) {
      mkdir($dir, 0777, true);
    }
    $payload = array(
        'dateTime' => date('Y-m-d H:i:s'),
        'class' => $class,
        'fileName' => $fileName ? basename($fileName) : null,
        'html' => $resultHtml,
    );
    file_put_contents($dir . 'result_' . $idUser . '.json', json_encode($payload));
  }
  
  public static function get($idUser) {
    self::ensureSessionStarted();
    $data = isset($_SESSION[self::sessionKey($idUser)]) ? $_SESSION[self::sessionKey($idUser)] : null;
    session_write_close();
    return $data;
  }
  
  public static function clear($idUser) {
    self::ensureSessionStarted();
    unset($_SESSION[self::sessionKey($idUser)]);
    session_write_close();
  }
  
  public static function getResultDir() {
    $pathSeparator = Parameter::getGlobalParameter('paramPathSeparator');
    $attachmentDirectory = Parameter::getGlobalParameter('paramAttachmentDirectory');
    return $attachmentDirectory . $pathSeparator . "import" . $pathSeparator;
  }
  
  public static function getLastResult($idUser) {
    $file = self::getResultDir() . 'result_' . $idUser . '.json';
    if (!file_exists($file)) {
      return null;
    }
    $payload = json_decode(file_get_contents($file), true);
    return $payload ? $payload : null;
  }
  
  public static function purgeLastResult($idUser) {
    $file = self::getResultDir() . 'result_' . $idUser . '.json';
    if (file_exists($file)) {
      unlink($file);
    }
  }
}